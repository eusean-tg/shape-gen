| Trial | Triangles | Boundary edges | Non-manifold edges | Peak allocated MiB |
|---|---:|---:|---:|---:|
| full/r384-iso0.glb | 245,520 | 0 | 6 | 2,517 |
| mini/r384-iso0.glb | 266,708 | 0 | 4 | 2,253 |
| mv-guidance3/r384-iso0.glb | 247,568 | 0 | 0 | 2,894 |
| mv-original-fixed/r384-iso0.glb | 256,908 | 0 | 6 | 1,347 |
| mv-resolutions/r192-iso0.glb | 62,648 | 0 | 0 | 2,294 |
| mv-resolutions/r192-iso-0.02.glb | 62,824 | 0 | 0 | 2,294 |
| mv-resolutions/r192-iso0.02.glb | 62,536 | 0 | 0 | 2,294 |
| mv-resolutions/r384-iso0.glb | 250,938 | 0 | 0 | 2,294 |
| mv-resolutions/r384-iso-0.02.glb | 251,476 | 0 | 0 | 2,294 |
| mv-resolutions/r384-iso0.02.glb | 250,448 | 0 | 0 | 2,294 |
| mv-resolutions/r512-iso0.glb | 446,130 | 0 | 0 | 2,294 |
| mv-resolutions/r512-iso-0.02.glb | 447,200 | 0 | 0 | 2,294 |
| mv-resolutions/r512-iso0.02.glb | 445,136 | 0 | 0 | 2,294 |
| mv-steps75/r384-iso0.glb | 250,580 | 0 | 0 | 2,894 |
| bpt-8192 | 2,302 | 16 | 5 | 2,059 |
| bpt-coverage | 2,511 | 9 | 0 | 2,085 |
| bpt-mv-original | 2,176 | 6 | 0 | 1,963 |
| bpt-mv512 | 2,230 | 24 | 5 | 1,984 |
| bpt-seed24680 | 2,551 | 7 | 2 | 2,096 |
| bpt-temp03 | 2,469 | 15 | 0 | 2,061 |

Memory is PyTorch allocation, not total GPU usage. Shape extraction trials that reuse a saved latent exclude diffusion sampling. All resolutions/levels in one trial share its run-level peak. Raw marching-cubes degenerate faces are included in the table; cleaned candidate metrics are recorded separately.
