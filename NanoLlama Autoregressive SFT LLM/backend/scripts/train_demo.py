from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ml.trainer import default_config, run_trial
from app.storage import Store

store = Store()
experiment_id = store.create_experiment("CLI demo", default_config())
trial_id = store.create_trial(experiment_id, default_config())
metrics = run_trial(store, experiment_id, trial_id, default_config(), steps=40)
store.update_experiment(experiment_id, status="completed", summary=metrics)
print(metrics)
