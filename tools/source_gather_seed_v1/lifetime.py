"""Private leases for the same already-loaded v7 engine, not a task authority."""
from context_base_v1 import FemaleGatherContext
from context_v2 import make_female_gather_seed_context

class GatherReadLifetimes:
 def __init__(self,engine):
  self.closed=False;self.generation=0;self.entries={}
  self.reader=make_female_gather_seed_context(FemaleGatherContext)(engine,read_scope=self.scope)
 def scope(self,identity):
  if self.closed or identity not in self.entries:raise ValueError('Current native Gather lifetime required')
  row=self.entries[identity]
  return {'owner':row['owner'],'epoch':row['epoch'],'active':row['active']}
 def bound_after_reset(self,identity):
  if self.closed:raise ValueError('Native Gather lifetimes disposed')
  self.invalidate(identity);self.generation+=1
  row={'owner':object(),'epoch':self.generation,'active':True};self.entries[identity]=row
  try:row['lease']=self.reader.bind(identity)
  except Exception:
   self.entries.pop(identity,None);raise
 def read(self,data):
  if not isinstance(data,dict)or set(data)!={'identity'}or not isinstance(data['identity'],str):raise ValueError('Exact internal scoped identity required')
  identity=data['identity'];self.scope(identity)
  return self.reader.read(self.entries[identity]['lease'])
 def invalidate(self,identity):
  row=self.entries.pop(identity,None)
  if row is None:return False
  row['active']=False
  if 'lease'in row:self.reader.invalidate(row['lease'])
  return True
 def dispose(self):
  if self.closed:return False
  for identity in list(self.entries):self.invalidate(identity)
  self.closed=True;self.reader.dispose();return True
