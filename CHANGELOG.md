# 2.0.0
- Switch python version to 3.6 (#30)

# 1.1.0
- fix a duplicate short hand options (#28)
- add shorthand option for description on create-job command (#29)

# 1.0.6
- add option export-log on training create-training-job command (#27)

# 1.0.5
- Relax restriction config.yaml for training (#26)
- Add help message for `training` sub-command (#24)
- Change var's name from `config/params` to `config_data` (#25)
- Relax the restriction of specifying `name` on `train-local` (#23)
- Update training config schema (#22)

# 1.0.4
- Convert to dict format (#17)
- add stop training job command (#18)
- configure pre-commit (#19)
- introduce isort (#20)

# 1.0.3
- Deprecate `/models` endpoint (#9)
- Add limit and offset options to commands (#10)
- テストの並列化 (#11)
- Remove test warnings (#15)
- Add `POST: /deployments/{deployment_id}/git/versions` (#16)

# 1.0.2
- Release to pypi with poetry (#7)

# 1.0.1
- Pass `destination` for retrying bucket upload file (#4)
- Change `User-Agent` when test (#3)
- Use server notebooktype start notebook (#5)

# 1.0.0
- initial release
