import os
import glob

pycache_dir = r'C:\Users\elias\PycharmProjects\PythonProject\__pycache__'
for f in glob.glob(os.path.join(pycache_dir, 'avatar_window*.pyc')):
    os.remove(f)
    print(f'Deleted: {f}')
