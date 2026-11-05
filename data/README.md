# Synthetic exports

`portfolio generate-data --out data` writes CSV and JSON versions of the same Jira-shaped tables. The generator uses only fictional people and projects. CI runs the generator, validates both formats, and uploads the generated files with the reports.

The seed is 2829 and the planning period is the third quarter of 2026. This data is an offline demonstration. It does not come from Jira or a company system.

The committed CSV and JSON files were generated in [CI run 42083080528](https://github.com/hamza2829/project-portfolio-tracker/actions/runs/42083080528). Subsequent CI runs compare both committed formats with a fresh generator result before importing meeting actions. The export contains 12 projects, 150 issues, 8 members, 24 milestones, 18 risks, 144 weekly updates, 153 allocation rows and 12 initial actions.
