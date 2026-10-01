# Retained DeepMesh compatibility layer

Copied from the tested `assets/makima-deepmesh/compat/lit_gpt` adapter for DeepMesh
revision 940d23ee2b5e4e94c565c800b49d6563c575c26d. Upstream code is under the
included Apache-2.0 license. The existing rotary and RMSNorm adapters use
FlashAttention Triton kernels in place of standalone extensions; checkpoint
weights and sampler semantics are unchanged. The API hashes these source files
in job provenance. The original experiment and its reports remain intact.
