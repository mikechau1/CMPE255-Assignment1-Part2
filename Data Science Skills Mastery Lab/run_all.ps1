<#
.SYNOPSIS
    Runs the whole lab: download data, execute all 46 skill demos, gate on coverage, build the site.

.NOTES
    Expect roughly 15-25 minutes on CPU. The LoRA fine-tune and the Fashion-MNIST CNN dominate.
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($name, $command) {
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & ([scriptblock]::Create($command))
    if ($LASTEXITCODE -ne 0) { throw "$name failed with exit code $LASTEXITCODE" }
    Write-Host ("--- {0} finished in {1:n0}s" -f $name, $sw.Elapsed.TotalSeconds) -ForegroundColor DarkGray
}

Step "Data acquisition"            "python pipeline/00_download_data.py"
Step "Phase 1 Business Understanding" "python pipeline/crisp01_business_understanding.py"
Step "Phase 2 Data Understanding"  "python pipeline/crisp02_data_understanding.py"
Step "Phase 3 Data Preparation"    "python pipeline/crisp03_data_preparation.py"
Step "Phase 4 Modeling (tabular)"  "python pipeline/crisp04_modeling.py"
Step "Phase 4 PyTorch (CNN)"       "python pipeline/heavy/pytorch_fashion.py"
Step "Phase 4 LoRA fine-tune"      "python pipeline/heavy/llm_finetune_lora.py"
Step "Phase 4 RAG retrieval"       "python pipeline/heavy/rag_pipeline.py"
Step "Phase 5 Evaluation"          "python pipeline/crisp05_evaluation.py"
Step "Phase 6 Deployment"          "python pipeline/crisp06_deployment.py"
Step "Phase 6 Model serving"       "python pipeline/heavy/serve_api.py"
Step "Coverage gate"               "python pipeline/skills_registry.py --check"

Write-Host ""
Write-Host "=== Site build ===" -ForegroundColor Cyan
Push-Location site
if (-not (Test-Path node_modules)) { npm install }
npm run build
Pop-Location

Write-Host ""
Write-Host "All 46 skills demonstrated. Run 'npm run preview' in site/ to view." -ForegroundColor Green
