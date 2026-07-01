resource "kind_cluster" "aegis_cluster" {
  name            = "aegis-production-cluster"
  wait_for_ready  = true

  # Lokalna ścieżka kubeconfig dla komunikacji z klastrem
  kubeconfig_path = pathexpand("~/.kube/config")

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    # ==========================================
    # CONTROL PLANE (node zarządzający)
    # ==========================================
    node {
      role = "control-plane"

      # Minimalna konfiguracja kubeadm (placeholder / kompatybilność)
      kubeadm_config_patches = [
        "kind: false"
      ]

      # Mapowanie portów hosta na klaster (Ingress / Gateway)
      extra_port_mappings {
        container_port = 80
        host_port      = 80
        listen_address = "127.0.0.1"
        protocol       = "TCP"
      }

      extra_port_mappings {
        container_port = 443
        host_port      = 443
        listen_address = "127.0.0.1"
        protocol       = "TCP"
      }
    }

    # ==========================================
    # WORKER NODE (runtime workloads)
    # ==========================================
    node {
      role = "worker"
    }
  }
}

output "kubeconfig" {
  # Ścieżka do kubeconfig generowanego przez KIND
  value       = kind_cluster.aegis_cluster.kubeconfig_path
  description = "Sciezka do pliku konfiguracyjnego kubeconfig"
}