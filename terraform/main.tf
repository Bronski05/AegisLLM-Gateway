resource "kind_cluster" "aegis_cluster" {
  name            = "aegis-production-cluster"
  wait_for_ready  = true
  kubeconfig_path = pathexpand("~/.kube/config")

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    # Węzeł zarządzający (Control Plane) + Ingress Edge Ports
    node {
      role = "control-plane"

      kubeadm_config_patches = [
        "kind: false"
      ]

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

    # Węzeł roboczy (Worker) - tutaj będą działać pody AegisLLM, Redis i Qdrant
    node {
      role = "worker"
    }
  }
}

output "kubeconfig" {
  value       = kind_cluster.aegis_cluster.kubeconfig_path
  description = "Sciezka do pliku konfiguracyjnego kubeconfig"
}