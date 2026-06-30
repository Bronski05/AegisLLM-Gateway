$Action = $args[0]

$HELM_PATH = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\helm.exe"

$CHART_DIR = "./aegisllm-chart"

$WORKER_NODE = "aegis-production-cluster-worker"



switch ($Action) {

    "up" {

        Write-Host "Starting Helm..." -ForegroundColor Green

        & $HELM_PATH upgrade --install aegis-release $CHART_DIR

        kubectl get pods

    }

    "down" {

        Write-Host "Removing from cluster..." -ForegroundColor Red

        & $HELM_PATH uninstall aegis-release

    }

    "build" {

        Write-Host "Rebuilding code..." -ForegroundColor Yellow

        docker build -t aegisllm-gateway:latest ./gateway

        docker save aegisllm-gateway:latest -o gateway.tar

        docker cp gateway.tar ${WORKER_NODE}:/gateway.tar

        docker exec -i $WORKER_NODE ctr -n "k8s.io" images import /gateway.tar

        rm gateway.tar

        kubectl rollout restart deployment aegis-gateway

        Write-Host "Done!" -ForegroundColor Green

    }

    "proxy" {

        Write-Host "Uruchamianie asynchronicznego port-forward dla całego stosu SRE..." -ForegroundColor Cyan

       

        # Bramka na 8080

        Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl port-forward svc/aegis-gateway-service 8080:80" -WindowStyle Minimized

        # Grafana na 3000

        Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl port-forward svc/aegis-grafana-service 3000:3000" -WindowStyle Minimized

        # Prometheus + Alertmanager na 9090 i 9093

        Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl port-forward svc/aegis-prometheus-service 9090:9090 9093:9093" -WindowStyle Minimized

       

        Write-Host "🚀 Bramka API:   http://localhost:8080" -ForegroundColor Green

        Write-Host "📊 Grafana:      http://localhost:3000" -ForegroundColor Green

        Write-Host "🔥 Prometheus:   http://localhost:9090" -ForegroundColor Green

        Write-Host "🔔 Alertmanager: http://localhost:9093" -ForegroundColor Green

    }

    "status" {

        kubectl get pods,svc

    }

    default {

        Write-Host "Options: up, down, build, proxy, status" -ForegroundColor Cyan

    }

} 

