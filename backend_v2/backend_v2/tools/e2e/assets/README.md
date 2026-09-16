# E2E image assets

Place the real test images used by the live E2E harness in this folder:

- `student_valid.jpg`: clear single face for the disposable E2E student.
- `student_second.jpg`: second clear single face of the same student.
- `no_face.jpg`: image with no detectable face.

The runner intentionally fails with a clear message when any configured image is missing. Do not commit real student photos or secrets.
