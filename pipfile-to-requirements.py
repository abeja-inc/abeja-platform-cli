#!python
# While we turned into using Pipenv for development, we still need
# `requirements.txt` for installation. This script reads `Pipfile` and
# generate `requirements.txt` from it.

import pipfile

pf = pipfile.load('Pipfile')
d = pf.data['default']

requirements = ['{}{}'.format(package, spec) for package, spec in pf.data['default'].items()]
print('\n'.join(requirements))
