"""Inference adapter: RMSNorm via FlashAttention's Triton kernel."""
from flash_attn.ops.triton.layer_norm import RMSNorm
FusedRMSNorm = RMSNorm
