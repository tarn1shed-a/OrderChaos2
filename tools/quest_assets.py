"""Recover QuestListHero layout and QuestHudNew callbacks/art, without SWF execution."""
import hashlib,io,json,struct
from pathlib import Path
from PIL import Image
from hud_assets import document,named_path,_ini_blocks,sprite_frames
from optimized_abc import parse_abc,extract_abc,named_method
from skill_icons import decode_localized_names
from ui_assets import Bits
from igm_frame_assets import recover_igm_frame

METHODS={
 'QuestListHero.initString':'2fd23042a16c9be2ba37cce4b9ba4fb978361a97743e53fe37a25a2bbbff87f7',
 'QuestListHero.getQuestList':'4a61cda6e462fc9916af21bb18b4277491eb015ef5c5c14e9d4dd4260c227f13',
 'QuestListHero.onEventQuestList':'f161fe380c2f95b0c8e335348ff7c643856d5ddd54e5b3dfc6417569a492a367',
 'QuestListHero.displayCurrQuest':'535c83191fd55efb1af5ccb3b2bb05016048f9cd7ec09e353450ee648f01e5a5',
 'QuestListHero.onListItemClick':'49355fd2c6c11577da3dcb915924e41d24fa4fa8124dbdee54eeb285de496dd0',
 'QuestListHero.onSetActive':'ebb6d3d4b3e32e93d6297f4c34595f448281408e36084dcbefff92ec8c061589',
 'QuestListHero.onAbandon':'df744aefc650a24880e49ba619c36f86b7cff7242c53660459599f52ec37d64b',
 'QuestHudNew.GetQuestStatus':'f7c3d58641ec5f9696821299649eeb33c163bc3710468f09e9a4bb8b38e65b49',
 'QuestHudNew.GetQuestInfo':'5d54cc0975520728014fcebbc595219bad268796729bf7ca74583ff91ac9f70d',
 'QuestHudNew.SetCurQuestItem':'b510e0688ce1cb5e7371ba2ddd1bc495c8c673d247c3cf7f62a06055e41041d5',
 'MoreQuestList.setItemData':'a33c8cb67100a359165b556067ace43425ad84064b131f8dd420493c1519995e',
}
def recover_quest_ui(extract,output,data):
 loaded={}
 def load(path):
  if path not in loaded:
   value=extract(path);loaded[path]=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
  return loaded[path]
 docs={name:document(load('ui/Flash/'+name+'.swf'),'ui/Flash/'+name+'.swf',root=name!='library') for name in ['QuestListHero','QuestHudNew','library']}
 config=_ini_blocks(load('ui/Config/interface_common_2.ini'))
 if not any(v.get('name')=='QuestHud' and v.get('url')=='QuestHudNew.swf' for v in config):raise ValueError('Quest HUD route changed')
 if not any(v.get('name')=='QuestListHero' and v.get('parent')=='IGMContainer' for v in config):raise ValueError('Quest book route changed')
 methods={}
 for name in ['QuestListHero','QuestHudNew']:
  abc=parse_abc(extract_abc(load('ui/Flash/'+name+'.swf')))
  for full,digest in METHODS.items():
   cls,method=full.split('.')
   if cls!=name and not (name=='QuestHudNew' and cls=='MoreQuestList'):continue
   found=named_method(abc,cls,method)
   if found['codeSHA256']!=digest:raise ValueError('Quest UI method changed; retrace required')
   methods[full]={k:v for k,v in found.items() if k!='instructions'}
 fields=['panel_list','panel_list.item_0','panel_list.item_1','panel_content.mc_content.txt_detail','titleScrollText','titleText','m_btnAbandon','m_btnSetActive','m_btnMap','reward_group','m_TextPrompt']
 book=docs['QuestListHero'];hud=docs['QuestHudNew'];lib=docs['library']
 if book['symbols']['Window_QuestListHeroInfo']!=100 or sprite_frames(book,100)[0][0]['characterId']!=99:raise ValueError('Quest book root changed')
 layout={field:named_path(book,99,field,lib) for field in fields}
 # Original empty-list path: no invented catalog, object inspector or diagram.
 keys=decode_localized_names(load('tables/String_General_.tbl'),'EN');zh=decode_localized_names(load('tables/String_General_zh.tbl'),'SC')
 key_ids={v:k for k,v in keys['values'].items()}
 strings={name:{'id':key_ids[name],'text':zh['values'][key_ids[name]]} for name in ['GENERAL_QUESTHUD_NOQUEST','GENERAL_FREEBAR_QUESTBOOK']}
 record=book['records'][layout['m_TextPrompt']['leafCharacterId']]
 if record[0]!=37:raise ValueError('Quest prompt is not source EditText')
 raw=record[1];bits=Bits(raw,2);bounds=bits.rect();at=bits.pos();flags=int.from_bytes(raw[at:at+2],'big');at+=2
 if flags&0x80 or not flags&0x100 or not flags&0x400 or not flags&0x20 or flags&0x200:raise ValueError('Quest prompt text flags changed')
 font_id,height=struct.unpack_from('<HH',raw,at);at+=4;color=list(raw[at:at+4]);at+=4
 align=raw[at];left,right,indent,leading=struct.unpack_from('<HHHh',raw,at+1)
 empty_style={'boundsPixels':[v/20 for v in bounds],'fontId':font_id,'fontHeight':height/20,'colorRGBA':color,
  'align':align,'marginsPixels':[left/20,right/20,indent/20],'leadingPixels':leading/20}
 hud_layout={field:named_path(hud,152,field,lib) for field in ['m_CurQuestPanel','m_QuestListPanel','m_QuestIconBtn']}
 destination=Path(output)/'ui';destination.mkdir(parents=True,exist_ok=True);assets={}
 for key,path in [('unfinished','head_obj/quest_unfinished.png'),('complete','head_obj/quest_complete.png'),('dailyComplete','head_obj/daily_quest_complete.png'),('failed','quest/quest_fail.png')]:
  source='ui/icons/'+path;raw=load(source);image=Image.open(io.BytesIO(raw))
  if image.size!=(96,96) or image.mode not in ('RGB','RGBA'):raise ValueError('Quest art dimensions changed')
  image.verify();filename='quest-'+key+'.png';(destination/filename).write_bytes(raw)
  assets[key]={'url':'/assets/ui/'+filename,'width':96,'height':96,'sourcePath':source,'sourceSHA256':hashlib.sha256(raw).hexdigest(),
   'sourceMethod':'QuestListHero.getQuestList','mode':'unchanged-full-source-png'}
 frame=recover_igm_frame(load,output)
 result={'format':'oc2-original-quest-ui-v3','frame':frame,'layouts':{'book':{'stagePixels':book['stagePixels'],'fields':layout},'hud':{'fields':hud_layout}},
  'methods':methods,'assets':assets,'data':data,'strings':strings,'emptyTextStyle':empty_style,
  'sources':{k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in loaded.items()},
  'provenance':{'swfScriptExecution':False,'originalServerStateAvailable':False,
   'limits':['Original list/detail/button transforms, the empty-list text branch and HUD quest-state icon paths are verified. The normalquest bitmap has metadata only and no exact external file was found.',
   'The game enables only the verified empty accepted-list branch in the recovered WindowContainerIGM frame. Catalog rows, research legends and object inspectors are not displayed as live game UI. Original nonempty quest processing, navigation history, DPI scaling and full text/filter rasterization remain incomplete.']}}
 (destination/'quests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
