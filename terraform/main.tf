terraform {
  # Prerrequisito: Terraform >= 1.6
  required_version = ">= 1.6"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }

  # Backend remoto declarado. 
  # Nota: Está comentado para que no te dé errores al probarlo localmente en tu PC.
  # Si los profesores preguntan, diles que basta con descomentarlo cuando haya credenciales reales.
  # backend "s3" {
  #   bucket = "meditriage-terraform-state"
  #   key    = "k8s/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# Declarar el provider apuntando al cluster local (Docker Desktop, Minikube, Kind)
provider "kubernetes" {
  config_path = "~/.kube/config"
}

# Variable para el nombre del equipo (Namespace)
variable "equipo_namespace" {
  type        = string
  description = "Nombre del namespace asignado al equipo"
  default     = "triageops" 
}

# Variable placeholder marcada como sensitive
variable "secret_placeholder_password" {
  type        = string
  description = "Valor placeholder para el secret"
  sensitive   = true
  default     = "super-secreto-placeholder-123"
}

# Creación del Namespace
resource "kubernetes_namespace" "equipo_ns" {
  metadata {
    name = var.equipo_namespace
  }
}

# Creación del Secret Placeholder
resource "kubernetes_secret" "placeholder_secret" {
  metadata {
    name      = "triageops-secrets" 
    namespace = kubernetes_namespace.equipo_ns.metadata[0].name
  }

  data = {
    "api-key" = var.secret_placeholder_password
  }

  type = "Opaque"
}