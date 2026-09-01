import torch

from app.ml.model import ModelConfig, NanoLlama


def test_model_forward_and_generation():
    model = NanoLlama(ModelConfig(max_seq_len=32, n_layer=2, n_head=2, n_embd=64))
    ids = torch.randint(0, 262, (2, 8))
    _, loss = model(ids, ids)
    assert loss.ndim == 0 and torch.isfinite(loss)
    output = model.generate(ids[:1], max_new_tokens=3)
    assert output.shape == (1, 11)
