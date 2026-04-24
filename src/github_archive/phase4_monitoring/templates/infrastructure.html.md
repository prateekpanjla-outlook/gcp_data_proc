## 1. Overview

`infrastructure.html` is a static reference page that documents the entire Terraform infrastructure across all four pipeline phases. It contains resource inventory tables, layer dependency diagrams, resource dependency graphs, Terraform state file layouts, and cross-phase dependency diagrams (data flow, shared resources, deploy/destroy order). No dynamic data is queried -- all content is hardcoded HTML.

## 2. Prerequisites

- Flask with Jinja2 templating (though no template variables are used -- the page is entirely static).
- No BigQuery queries or runtime data are required.

## 3. Upstream & Downstream Dependencies

**Upstream (what renders this template)**:
- `app.py` route `/infra` -- calls `render_template('infrastructure.html')` with no query data.

**Downstream (what this template links to)**:
- Navigation links to all other dashboard pages.

**Referenced infrastructure (documented but not queried)**:
- Phase 1 Terraform: `infrastructure/github_archive/phase1_ingestion/terraform/` -- single-layer setup (AR repo, Cloud Run Job, Scheduler, SAs).
- Phase 2 Terraform: `infrastructure/github_archive/phase2_processfiles/terraform/layers/01_static|02_first_time|03_operational/` -- 3-layer setup.
- Phase 3 Terraform: `infrastructure/github_archive/phase3_loadbigquery/terraform/layers/01_static|02_first_time|03_operational/` -- 3-layer setup.
- Phase 4 Terraform: `infrastructure/github_archive/phase4_monitoring/terraform/layers/01_static|02_first_time|03_operational/` -- 3-layer setup.

## 4. Code Walkthrough

1. **Styles (lines 5-98)**: Extensive inline CSS for multiple diagram types: layer diagrams (`.tf-layers`, `.tf-phase`, `.tf-layer`), resource dependency graphs (`.res-graph`, `.res-phase`, `.res-box`), state flow diagrams (`.state-flow`, `.state-box`), and dependency flow diagrams (`.dep-flow`, `.gbox`). Colour-coded by phase: Phase 1 blue, Phase 2 green, Phase 3 yellow, Phase 4 red.

2. **Resource inventory tables (lines 113-209)**: Four sections (one per phase) listing every Terraform resource with its type, name, and purpose. Phases 2-4 are subdivided by layer (01_static, 02_first_time, 03_operational).

3. **Diagram 1 -- Layer Dependencies (lines 214-279)**: Side-by-side boxes for each phase showing the layer deployment order with downward arrows between layers.

4. **Diagram 2 -- Resource Dependency Graph (lines 284-380)**: Per-phase `depends_on` relationships. Shows SA -> IAM -> build -> compute chains. Includes a colour legend: yellow = SA, green = storage, blue = compute, red = IAM, purple outline = null_resource.

5. **Diagram 3 -- Terraform State Files (lines 385-462)**: Shows each phase's state file count and approximate resource counts. Notes that state is local (no remote backend) and values are passed between layers/phases via `-var` flags.

6. **Cross-Phase Dependencies (lines 467-538)**: Three subsections:
   - Data Flow: vertical diagram from GCS Landing through processing to BigQuery to Dashboard.
   - Shared Resources: Cloud Build SA and Artifact Registry (created in Phase 1, used by all phases).
   - Deploy/Destroy Order: Phase 1 -> 2 -> 3 -> 4 (deploy), Phase 4 -> 3 -> 2 -> 1 (destroy).
