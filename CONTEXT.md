---
type: repository
status: active
owner_repo: MohammedAbdelshafy/suez-cad-generator
product_name: suez-cad-generator
source_of_truth: https://github.com/MohammedAbdelshafy/suez-cad-generator
---

# suez-cad-generator CONTEXT

One job: estimate concept-level port dimensions from design vessel inputs and render a schematic plan for engineering review.

## Inputs
- Setup and engineering basis: [README](README.md)
- Backend: [backend](backend/)
- Browser UI: [static](static/)
- Supporting deliverable: [Suez Port Masterplan](https://github.com/MohammedAbdelshafy/Suez_Port_Masterplan)

## Process
1. Enter the design vessel's dimensions and selected port assumptions.
2. Calculate the supported channel, turning, berth and quay dimensions.
3. Render a schematic plan and export supported formats.
4. Review assumptions and warnings with a qualified maritime engineer.
5. Keep these concept results separate from construction-ready design.

## Output
A concept-level dimensional summary and schematic plan with export files.

## Check
Run the repository tests and verify the calculations and exports. Results are planning estimates, not an approved design or construction specification.
