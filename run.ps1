
# =========================
# Skrypt operacyjny do zarządzania lokalnym środowiskiem:
# - deployment Helm
# - build obrazu
# - port-forwarding
# - status klastra


$Action = $args[0]

# Ścieżka do lokalnej instalacji Helm (WinGet)
$HELM_PATH = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\helm.exe"

# Lokalizacja charta Helm
$CHART_DIR = "./aegisllm-chart"

# Nazwa node’a KIND używana do ręcznego importu obrazów
$WORKER_NODE = "aegis-production-cluster-worker"


switch ($Action) {

    "up" {
        # =========================================
        # DEPLOY STACK (Helm install/upgrade)
        # =========================================
        Write-Host "Starting Helm..." -ForegroundColor Green

        # Instalacja lub aktualizacja release w Kubernetes
        & $HELM_PATH upgrade --install aegis-release $CHART_DIR

        # Podgląd statusu podów po deployu
        kubectl get pods
    }

    "down" {
        # =========================================
        # TEARDOWN STACK
        # =========================================
        Write-Host "Removing from cluster..." -ForegroundColor Red

        # Usunięcie release Helm
        & $HELM_PATH uninstall aegis-release
    }

    "build" {
        # =========================================
        # BUILD + LOAD IMAGE INTO KIND
        # =========================================
        Write-Host "Rebuilding code..." -ForegroundColor Yellow

        # Budowa obrazu gatewaya
        docker build -t aegisllm-gateway:latest ./gateway

        # Eksport obrazu do pliku tar
        docker save aegisllm-gateway:latest -o gateway.tar

        # Transfer obrazu do node’a KIND
        docker cp gateway.tar ${WORKER_NODE}:/gateway.tar

        # Import obrazu do containerd w klastrze KIND
        docker exec -i $WORKER_NODE ctr -n "k8s.io" images import /gateway.tar

        # Cleanup lokalnego artefaktu
        rm gateway.tar

        # Restart deploymentu aby wymusić reload obrazu
        kubectl rollout restart deployment aegis-gateway

        Write-Host "Done!" -ForegroundColor Green
    }

    "proxy" {
        # =========================================
        # LOCAL ACCESS TO CLUSTER SERVICES
        # =========================================
        Write-Host "Uruchamianie asynchronicznego port-forward dla całego stosu SRE..." -ForegroundColor Cyan

        # Gateway API (entrypoint systemu)
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl port-forward svc/aegis-gateway-service 8080:80" -WindowStyle Minimized

        # Grafana dashboardy
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl port-forward svc/aegis-grafana-service 3000:3000" -WindowStyle Minimized

        # Prometheus + Alertmanager (metryki + alerting)
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl port-forward svc/aegis-prometheus-service 9090:9090 9093:9093" -WindowStyle Minimized

        # Informacje użytkowe (lokalne endpointy)
        Write-Host "🚀 Bramka API:   http://localhost:8080" -ForegroundColor Green
        Write-Host "📊 Grafana:      http://localhost:3000" -ForegroundColor Green
        Write-Host "🔥 Prometheus:   http://localhost:9090" -ForegroundColor Green
        Write-Host "🔔 Alertmanager: http://localhost:9093" -ForegroundColor Green
    }

    "status" {
        # =========================================
        # CLUSTER STATE OVERVIEW
        # =========================================
        kubectl get pods,svc
    }

    default {
        # =========================================
        # HELP / USAGE
        # =========================================
        Write-Host "Options: up, down, build, proxy, status" -ForegroundColor Cyan
    }
}