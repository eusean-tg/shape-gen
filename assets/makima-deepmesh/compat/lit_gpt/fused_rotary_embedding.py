"""Inference adapter: same NeoX rotation via FlashAttention's Triton kernel."""
from flash_attn.layers.rotary import apply_rotary_emb as apply_rotary_emb_func
