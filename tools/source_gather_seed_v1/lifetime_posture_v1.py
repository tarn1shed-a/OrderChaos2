"""Reuse the frozen same-engine lease lifecycle with an extended read class."""
from lifetime import GatherReadLifetimes as ExistingLifetimes
from context_posture_v1 import make_posture_checked_context

class GatherReadLifetimes(ExistingLifetimes):
 def __init__(self,engine):
  super().__init__(engine)
  base=type(self.reader);self.reader.dispose()
  self.reader=make_posture_checked_context(base)(engine,read_scope=self.scope)
