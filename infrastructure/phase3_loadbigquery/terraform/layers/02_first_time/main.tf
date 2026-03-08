# Layer 02: First-time Resources
# These resources require APIs to be enabled first
# Apply once, re-apply only if changes are needed

# NOTE: Eventarc service agent IAM bindings moved to Layer 02
# because Eventarc triggers can APIs to be enabled first

# (they require the Eventarc APIs to be enabled in a state)

# so we use Layer 02 outputs to instead

# API enablement
data "terraform_remote_state" "static" {
  backend = "local"

  config = {
    path = "../01_static/terraform.tfstate"
  }
}

data "terraform_remote_state" "first_time" {
  backend = "local"
  config = {
    path = "../02_first_time/terraform.tfstate"
  }
}

data "terraform_remote_state" "phase2_static" {
  backend = "local"
  config = {
    path = "../phase2_process_files/terraform/layers/01_static/terraform.tfstate"
  }
}
