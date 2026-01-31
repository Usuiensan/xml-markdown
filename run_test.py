import importlib.util,traceback,sys
spec=importlib.util.spec_from_file_location('mod','xml-to-md.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    mod.process_from_file('道路交通法.xml', True)
except Exception:
    traceback.print_exc()
    sys.exit(1)
print('done')
