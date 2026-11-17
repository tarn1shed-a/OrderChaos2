"""Common source loaded-track queue snapshot; no tick, decoder/renderer clone.

Consumes already-bound current native queue/track objects. Scalar record layout
is the same88B used by frozen SourceLayerQueue, with original control clock and
loop setter11967dc. Raw native pointers are never included in the result.
"""
import math,struct
F=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]

def read_record(e,at):
 raw=bytes(e.uc.mem_read(at,0x58));name=raw[:64]
 if b'\0'not in name:raise ValueError('Native88B record name lacks bounded NUL')
 name=name.split(b'\0')[0].decode('utf-8')
 if not name:return None
 flags,speed,begin,blend=struct.unpack_from('<I3f',raw,64)
 if struct.unpack_from('<Q',raw,0x50)[0]:raise ValueError('Unrecovered per-clip event provider')
 if not all(math.isfinite(x)for x in(speed,begin,blend))or speed!=1 or begin<0:raise ValueError('Uncovered native loaded record speed/clock')
 return {'name':name,'flags':flags,'speed':speed,'begin':begin,'blend':blend}

def read_source_queue(e,identity):
 if identity not in e.humans or e.actors.get(identity)is not e.humans[identity]['actor']:raise ValueError('Current same actual native actor required')
 h=e.humans[identity];q=h['q'];engine=q['engine'];channels=[];rawflags=[]
 if e.r(engine+0x18,'I')[0]!=3 or len(q['layers'])!=2:raise ValueError('Actual two-layer engine flags3 required')
 def clock(p):
  if p is None:return None
  clip=p['clip'];r=e.profile['ranges'].get(clip)
  if r is None or p['startMs']!=r['startMs']:raise ValueError('Native own clock/range identity differs')
  age=F(e.r(p['control']+8,'f')[0]-p['startMs']);loop=e.r(p['control']+0x29,'B')[0]
  if loop not in(0,1)or not math.isfinite(age)or not 0<=age<=r['endMs']-r['startMs']:raise ValueError('Native source clock not admitted')
  return {'clip':clip,'ageMs':age,'loop':p['loop'],'_clockLoop':bool(loop)}
 for c,layer in enumerate(q['layers']):
  flag=e.r(engine+0x10+c*4,'B')[0];rawflags.append(flag)
  record=read_record(e,engine+0x38+c*0x58);default=read_record(e,engine+0x5a0+c*0x58)
  base=engine+c*0x218;head=e.r(base+0x2f8,'b')[0];count=e.r(base+0x2fa,'b')[0]
  if not 0<=head<6 or not 0<=count<=6:raise ValueError('Original six-entry ring outside source bounds')
  pending=[read_record(e,base+0xe8+((head+i)%6)*0x58)for i in range(count)]
  if any(x is None for x in pending):raise ValueError('Native pending record lacks name')
  current,previous=clock(layer['current']),clock(layer['previous'])
  if current is None or record is None or current['clip']!=record['name']:raise ValueError('Current original selected native track not available yet')
  duration,remaining=e.r(layer['blendNode']+0xb4,'2I')
  if remaining>duration:raise ValueError('Native blend lifetime outside source subset')
  channels.append({'record':record,'defaultRecord':default,'pending':pending,'needSelect':bool(flag&16),'completed':bool(flag&1),'current':current,'previous':previous,'sequence':layer['sequence'],'remainingMs':remaining,'durationMs':duration,'completionCount':layer['completions']})
 return {'format':'oc2-source-world-track-initial-v1','channels':channels,'originalRawFlags':rawflags,'currentActorSameNativeQueue':True,'sequenceAndCompletionsAreExistingHostObservationCounters':True,'tickOrQualificationProduced':False}
