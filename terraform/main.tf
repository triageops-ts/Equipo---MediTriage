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
  # backend "s3" {
  #   bucket = "meditriage-terraform-state"
  #   key    = "k8s/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# Provider Kubernetes
provider "kubernetes" {
  config_path = "~/.kube/config"
}

# Variable para el nombre del equipo
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

# Variable para identificar el ambiente
variable "ambiente" {
  type        = string
  description = "Ambiente de despliegue"
  default     = "local"
}

# Etiquetas comunes para FinOps (S12-14)
locals {
  finops_tags = {
    proyecto    = "meditriage"
    ambiente    = var.ambiente
    responsable = "triageops"
  }
}

# Creación del Namespace
resource "kubernetes_namespace" "equipo_ns" {
  metadata {
    name   = var.equipo_namespace
    labels = local.finops_tags
  }
}

# Creación del Secret Placeholder
resource "kubernetes_secret" "placeholder_secret" {
  metadata {
    name      = "triageops-secrets"
    namespace = kubernetes_namespace.equipo_ns.metadata[0].name
    labels    = local.finops_tags
  }

  data = {
    "api-key" = var.secret_placeholder_password
  }

  type = "Opaque"
}
