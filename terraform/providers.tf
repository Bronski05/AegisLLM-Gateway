# ==========================================
# Terraform core configuration
# ==========================================

terraform {
  # Minimalna wersja Terraform wymagana do uruchomienia projektu
  required_version = ">= 1.0"

  # Deklaracja providerów używanych w infrastrukturze
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "0.6.0"
    }
  }
}

# Provider KIND – umożliwia tworzenie lokalnych klastrów Kubernetes w Dockerze
provider "kind" {}