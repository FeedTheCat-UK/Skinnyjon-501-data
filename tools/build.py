#!/usr/bin/env python3
"""Builds the Football 501 player lists and game categories from the transfermarkt-datasets CSVs.
Usage: python3 tools/build.py /path/to/folder-with-csv.gz
Writes: players/current.json, players/former.json, game/names.json, game/cats.json, game/meta.json"""
import sys, json, re, pathlib, datetime
import pandas as pd
SRC=pathlib.Path(sys.argv[1]); OUT=pathlib.Path(__file__).resolve().parent.parent
LEAGUES={'GB1':'Premier League','ES1':'LaLiga','IT1':'Serie A','L1':'Bundesliga','FR1':'Ligue 1'}
CLUB_NAMES={'Associazione Sportiva Roma':'Roma','Società Sportiva Lazio S.p.A.':'Lazio','Bologna Football Club 1909':'Bologna',
 '1. Fußballclub Heidenheim 1846':'Heidenheim','Atlético de Madrid':'Atlético Madrid','Sunderland AFC':'Sunderland','AFC Bournemouth':'Bournemouth',
 'SSC Napoli':'Napoli','Juventus FC':'Juventus','FC Girondins Bordeaux':'Bordeaux','Stade Rennais FC':'Rennes','RC Strasbourg Alsace':'Strasbourg',
 'LOSC Lille':'Lille','ESTAC Troyes':'Troyes','Thonon Évian Grand Genève FC':'Evian','Parma Calcio 1913':'Parma','US Salernitana 1919':'Salernitana',
 'Como 1907':'Como','Pisa Sporting Club':'Pisa','Delfino Pescara 1936':'Pescara','TSG 1899 Hoffenheim':'Hoffenheim','Bayer 04 Leverkusen':'Bayer Leverkusen',
 '1.FSV Mainz 05':'Mainz 05','1.FC Köln':'1. FC Köln','1.FC Nuremberg':'Nuremberg','1.FC Union Berlin':'Union Berlin','SV Werder Bremen':'Werder Bremen',
 'FC Schalke 04':'Schalke 04','SpVgg Greuther Fürth':'Greuther Fürth','Real Betis Balompié':'Real Betis','RCD Espanyol Barcelona':'Espanyol',
 'Celta de Vigo':'Celta Vigo','Deportivo de La Coruña':'Deportivo La Coruña','Real Valladolid CF':'Real Valladolid','Olympique Marseille':'Marseille',
 'Olympique Lyon':'Lyon','Paris Saint-Germain':'Paris Saint-Germain','AS Saint-Étienne':'Saint-Étienne','Stade Brestois 29':'Brest','Stade Reims':'Reims',
 'FC Sochaux-Montbéliard':'Sochaux','AS Nancy-Lorraine':'Nancy','Nîmes Olympique':'Nîmes','Montpellier HSC':'Montpellier','Angers SCO':'Angers',
 'Clermont Foot 63':'Clermont','Dijon FCO':'Dijon','Le Havre AC':'Le Havre','OGC Nice':'Nice','SM Caen':'Caen','SC Bastia':'Bastia','EA Guingamp':'Guingamp',
 'RC Lens':'Lens','AJ Auxerre':'Auxerre','AS Monaco':'Monaco','Valenciennes FC':'Valenciennes','Amiens SC':'Amiens','AC Ajaccio':'AC Ajaccio','GFC Ajaccio':'GFC Ajaccio',
 'Hellas Verona':'Hellas Verona','Chievo Verona':'Chievo','Atalanta BC':'Atalanta','ACF Fiorentina':'Fiorentina','UC Sampdoria':'Sampdoria','Genoa CFC':'Genoa',
 'Udinese Calcio':'Udinese','Cagliari Calcio':'Cagliari','Brescia Calcio':'Brescia','Benevento Calcio':'Benevento','Frosinone Calcio':'Frosinone','Spezia Calcio':'Spezia',
 'Catania FC':'Catania','Cesena FC':'Cesena','Siena FC':'Siena','US Livorno 1915':'Livorno','AC Carpi':'Carpi','FC Crotone':'Crotone','AC Monza':'Monza','US Sassuolo':'Sassuolo',
 'US Lecce':'Lecce','US Cremonese':'Cremonese','Torino FC':'Torino','Venezia FC':'Venezia','Palermo FC':'Palermo','FC Empoli':'Empoli','SPAL':'SPAL',
 'Real Zaragoza':'Real Zaragoza','Sevilla FC':'Sevilla','Valencia CF':'Valencia','Villarreal CF':'Villarreal','Málaga CF':'Málaga','Córdoba CF':'Córdoba','Elche CF':'Elche',
 'Getafe CF':'Getafe','Granada CF':'Granada','Cádiz CF':'Cádiz','Girona FC':'Girona','UD Almería':'Almería','Levante UD':'Levante','UD Las Palmas':'Las Palmas',
 'RCD Mallorca':'Mallorca','CA Osasuna':'Osasuna','SD Eibar':'Eibar','SD Huesca':'Huesca','CD Leganés':'Leganés','Deportivo Alavés':'Alavés','Sporting Gijón':'Sporting Gijón',
 'Real Oviedo':'Real Oviedo','FC Barcelona':'Barcelona','RB Leipzig':'RB Leipzig','FC Augsburg':'Augsburg','SC Freiburg':'Freiburg','VfB Stuttgart':'Stuttgart',
 'VfL Bochum':'Bochum','VfL Wolfsburg':'Wolfsburg','Hamburger SV':'Hamburg','Hertha BSC':'Hertha Berlin','SV Darmstadt 98':'Darmstadt','SC Paderborn 07':'Paderborn',
 'FC St. Pauli':'St. Pauli','FC Ingolstadt 04':'Ingolstadt','Eintracht Braunschweig':'Eintracht Braunschweig','Holstein Kiel':'Holstein Kiel','Arminia Bielefeld':'Arminia Bielefeld',
 'Bayern Munich':'Bayern Munich','FC Metz':'Metz','FC Toulouse':'Toulouse','FC Nantes':'Nantes','FC Lorient':'Lorient','Paris FC':'Paris FC'}
def club_name(n):
    if n in CLUB_NAMES: return CLUB_NAMES[n]
    return re.sub(r'\s+(FC|AFC)$','',n).strip()
NATION_ADJ={'England':'English','France':'French','Spain':'Spanish','Germany':'German','Italy':'Italian','Brazil':'Brazilian','Argentina':'Argentine',
 'Netherlands':'Dutch','Portugal':'Portuguese','Belgium':'Belgian','Scotland':'Scottish','Wales':'Welsh','Ireland':'Irish','Northern Ireland':'Northern Irish',
 'Denmark':'Danish','Sweden':'Swedish','Norway':'Norwegian','Switzerland':'Swiss','Austria':'Austrian','Croatia':'Croatian','Serbia':'Serbian','Senegal':"Senegalese",
 "Cote d'Ivoire":'Ivorian','Nigeria':'Nigerian','Ghana':'Ghanaian','Cameroon':'Cameroonian','Morocco':'Moroccan','Algeria':'Algerian','Uruguay':'Uruguayan',
 'Colombia':'Colombian','Poland':'Polish','Czech Republic':'Czech','United States':'American','Japan':'Japanese','Mali':'Malian','Greece':'Greek','Türkiye':'Turkish'}
D=SRC
ap=pd.read_csv(D/'appearances.csv.gz',usecols=['game_id','player_id','player_club_id','competition_id','yellow_cards','red_cards','goals'])
g=pd.read_csv(D/'games.csv.gz',usecols=['game_id','season'])
pl=pd.read_csv(D/'players.csv.gz')
cl=pd.read_csv(D/'clubs.csv.gz').set_index('club_id')
a=ap[ap.competition_id.isin(LEAGUES)].merge(g,on='game_id')
seasons=(int(a.season.min()),int(a.season.max()))
a['cards']=a.yellow_cards+a.red_cards
# per player per club per league
pc=a.groupby(['player_id','player_club_id','competition_id']).agg(apps=('game_id','count'),goals=('goals','sum'),yel=('yellow_cards','sum'),red=('red_cards','sum'),cards=('cards','sum'),first=('season','min'),last=('season','max')).reset_index()
pids=set(pc.player_id)
pl=pl[pl.player_id.isin(pids)].copy()
pl['yob']=pd.to_datetime(pl.date_of_birth,errors='coerce').dt.year
tot=pc.groupby('player_id').apps.sum()
pl['tot']=pl.player_id.map(tot).fillna(0)
pl=pl.sort_values('tot',ascending=False).reset_index(drop=True)
idx={pid:i for i,pid in enumerate(pl.player_id)}
latest=int(pl.last_season.max())
def nat(r): v=r.country_of_citizenship; return v if isinstance(v,str) else ''
def ival(v): return int(v) if v==v and v is not None else None
# ---- player lists (full detail) ----
cur,old=[],[]
pcg=pc.groupby('player_id')
for r in pl.itertuples():
    clubs=[]
    for c in pcg.get_group(r.player_id).sort_values('first').itertuples():
        clubs.append({'club':club_name(cl.name.get(c.player_club_id,str(c.player_club_id))),'club_id':int(c.player_club_id),'league':LEAGUES[c.competition_id],
                      'seasons':f'{c.first}/{str(c.first+1)[-2:]}–{c.last}/{str(c.last+1)[-2:]}','apps':int(c.apps),'goals':int(c.goals),'yellow':int(c.yel),'red':int(c.red)})
    rec={'id':int(r.player_id),'name':r.name,'nation':nat(r),'born':ival(r.yob),'position':r.position if isinstance(r.position,str) else '',
         'clubs':clubs}
    (cur if r.last_season==latest else old).append(rec)
(OUT/'players').mkdir(exist_ok=True); (OUT/'game').mkdir(exist_ok=True)
json.dump({'note':'Players who appeared in the 2025/26 squad data','players':cur},open(OUT/'players/current.json','w'),ensure_ascii=False,indent=0)
json.dump({'note':'Players no longer in the dataset\'s leagues (retired or moved on). Static.','players':old},open(OUT/'players/former.json','w'),ensure_ascii=False,indent=0)
# ---- game: names for autocomplete ----
names=[[r.name, nat(r), ival(r.yob) or 0] for r in pl.itertuples()]
json.dump(names,open(OUT/'game/names.json','w'),ensure_ascii=False,separators=(',',':'))
# ---- game: categories ----
TIERS=[(501,180),(301,120),(201,80),(101,40),(51,20)]
def tier(vals):
    for start,mx in TIERS:
        e=sorted(v for v in vals if 1<=v<=mx)
        if len(e)>=20 and sum(e[-8:])>=start*1.15: return start
    return None
cats=[]
SW={'apps':'appearances','goals':'goals','cards':'cards (yellow + red)'}
def add(cid,kind,label,sub,stat,series,weight,note=''):
    vals={idx[p]:int(v) for p,v in series.items() if v>0 and p in idx}
    st=tier(list(vals.values()))
    if not st: return
    cats.append({'id':cid,'kind':kind,'stat':stat,'label':label,'sub':sub,'note':note,'start':st,'w':round(weight,2),'p':sorted([[k,v] for k,v in vals.items()],key=lambda x:-x[1])})
span=f"{seasons[0]}/{str(seasons[0]+1)[-2:]}–{seasons[1]}/{str(seasons[1]+1)[-2:]}"
# Categories are kept generic: whole leagues, all five leagues together, and only the best-known clubs.
BIG_CLUBS={985:'Manchester United',281:'Manchester City',31:'Liverpool',11:'Arsenal',631:'Chelsea',148:'Tottenham Hotspur',
 762:'Newcastle United',29:'Everton',405:'Aston Villa',379:'West Ham United',
 418:'Real Madrid',131:'Barcelona',13:'Atlético Madrid',
 506:'Juventus',5:'AC Milan',46:'Inter Milan',12:'Roma',6195:'Napoli',398:'Lazio',
 27:'Bayern Munich',16:'Borussia Dortmund',15:'Bayer Leverkusen',
 583:'Paris Saint-Germain',244:'Marseille',1041:'Lyon',162:'Monaco'}
WORD={'apps':'appearances','goals':'goals','cards':'cards (yellow + red)'}
CAP={'apps':'Most appearances','goals':'Most goals','cards':'Most cards (yellow + red)'}
# whole leagues: "Most Premier League appearances" etc.
for comp,grp in pc.groupby('competition_id'):
    for stat in ['apps','goals','cards']:
        add(f'l{comp}{stat[0]}','league',LEAGUES[comp],CAP[stat],stat,grp.groupby('player_id')[stat].sum(),2.0 if stat!='cards' else 1.0)
# all five leagues together
for stat in ['apps','goals','cards']:
    add(f'all{stat[0]}','all','All five leagues',CAP[stat],stat,pc.groupby('player_id')[stat].sum(),1.5 if stat!='cards' else 0.8)
# the big clubs (league games for that club)
for (club,comp),grp in pc[pc.player_club_id.isin(list(BIG_CLUBS))].groupby(['player_club_id','competition_id']):
    for stat in ['apps','goals']:
        add(f'c{club}{stat[0]}','club',BIG_CLUBS[club],f'{LEAGUES[comp]} {WORD[stat]}',stat,grp.groupby('player_id')[stat].sum(),1.0)
# (country caps are left out: the dataset mixes youth and senior caps, so they can't be trusted)
meta={'version':1,'built':datetime.date.today().isoformat(),'seasons':span,'leagues':list(LEAGUES.values()),
      'coverage':f'League stats: {", ".join(LEAGUES.values())}, {span} seasons (league matches only).',
      'players':len(names),'categories':len(cats),'source':'transfermarkt-datasets by David Cariboo (CC0)'}
json.dump(cats,open(OUT/'game/cats.json','w'),ensure_ascii=False,separators=(',',':'))
json.dump(meta,open(OUT/'game/meta.json','w'),ensure_ascii=False,indent=1)
print(meta); print('current',len(cur),'former',len(old))
import collections; print(collections.Counter((c['kind'],c['stat'],c['start']) for c in cats))
