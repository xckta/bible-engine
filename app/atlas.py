from __future__ import annotations

PLACES=[
{'id':'jerusalem','name':'Jerusalem','lat':31.778,'lon':35.235,'region':'Judea','refs':['2 Samuel 5','Psalm 48','Luke 19–24'],'note':'Approximate city center.'},
{'id':'bethlehem','name':'Bethlehem','lat':31.705,'lon':35.202,'region':'Judea','refs':['Ruth 1–4','Micah 5:2','Matthew 2'],'note':'Approximate.'},
{'id':'jericho','name':'Jericho','lat':31.871,'lon':35.444,'region':'Jordan Valley','refs':['Joshua 6','Luke 19'],'note':'Approximate ancient-site area.'},
{'id':'nazareth','name':'Nazareth','lat':32.700,'lon':35.303,'region':'Galilee','refs':['Luke 1–4','Matthew 2:23'],'note':'Approximate.'},
{'id':'capernaum','name':'Capernaum','lat':32.881,'lon':35.575,'region':'Galilee','refs':['Mark 1–2','Matthew 4'],'note':'Approximate archaeological-site area.'},
{'id':'samaria','name':'Samaria','lat':32.277,'lon':35.189,'region':'Samaria','refs':['1 Kings 16','2 Kings 17','Acts 8'],'note':'Sebaste/Samaria area.'},
{'id':'mount-carmel','name':'Mount Carmel','lat':32.731,'lon':35.047,'region':'Carmel','refs':['1 Kings 18'],'note':'Mountain-range marker.'},
{'id':'sea-galilee','name':'Sea of Galilee','lat':32.82,'lon':35.59,'region':'Galilee','refs':['Mark 4–6','John 6'],'note':'Water-body center.'},
{'id':'dead-sea','name':'Dead Sea','lat':31.50,'lon':35.50,'region':'Arabah','refs':['Genesis 14'],'note':'Water-body center.'},
{'id':'damascus','name':'Damascus','lat':33.513,'lon':36.292,'region':'Syria','refs':['2 Kings 5','Acts 9'],'note':'Approximate historic center.'},
{'id':'antioch','name':'Antioch on the Orontes','lat':36.202,'lon':36.160,'region':'Syria','refs':['Acts 11–15'],'note':'Modern Antakya area.'},
{'id':'ephesus','name':'Ephesus','lat':37.941,'lon':27.342,'region':'Asia Minor','refs':['Acts 19','Ephesians'],'note':'Archaeological-site area.'},
{'id':'corinth','name':'Corinth','lat':37.938,'lon':22.927,'region':'Achaia','refs':['Acts 18','1 Corinthians','2 Corinthians'],'note':'Ancient Corinth area.'},
{'id':'rome','name':'Rome','lat':41.890,'lon':12.492,'region':'Italy','refs':['Romans','Acts 28'],'note':'Historic-city marker.'},
{'id':'nineveh','name':'Nineveh','lat':36.359,'lon':43.152,'region':'Assyria','refs':['Jonah','Nahum'],'note':'Ancient-site area near Mosul.'},
{'id':'babylon','name':'Babylon','lat':32.536,'lon':44.421,'region':'Babylonia','refs':['2 Kings 24–25','Daniel 1'],'note':'Ancient-site area.'},
{'id':'ur','name':'Ur','lat':30.963,'lon':46.103,'region':'Mesopotamia','refs':['Genesis 11:28–31'],'note':'Traditional identification at Tell el-Muqayyar.'},
{'id':'sinai','name':'Sinai traditional region','lat':28.539,'lon':33.975,'region':'Sinai Peninsula','refs':['Exodus 19–34'],'note':'Marker follows traditional Mount Sinai region; identification is debated.'},
]

TEMPLE={
'name':'Jerusalem Temple schematic','notice':'Schematic teaching/research model, not a claim that every biblical/Second Temple phase had an identical plan.',
'components':[
{'id':'outer','name':'Outer court / precinct','x':5,'y':5,'w':90,'h':90,'refs':['1 Kings 6–8','2 Chronicles 3–5']},
{'id':'altar','name':'Altar area','x':18,'y':36,'w':14,'h':22,'refs':['2 Chronicles 4:1']},
{'id':'porch','name':'Porch / vestibule','x':48,'y':28,'w':12,'h':44,'refs':['1 Kings 6:3']},
{'id':'holy','name':'Holy Place','x':60,'y':28,'w':22,'h':44,'refs':['1 Kings 6:17']},
{'id':'most-holy','name':'Most Holy Place','x':82,'y':34,'w':13,'h':32,'refs':['1 Kings 6:16–20']},
]}

COSMOLOGY={
'name':'Biblical cosmological imagery — schematic map','notice':'This is a map of recurring textual images, not a claim that every biblical author held one technical cosmological model.',
'layers':[
{'id':'heavens','name':'Heavens / heaven of heavens','y':5,'h':15,'refs':['Deuteronomy 10:14','1 Kings 8:27','Psalm 148:4']},
{'id':'waters-above','name':'Waters above','y':20,'h':12,'refs':['Genesis 1:7','Psalm 148:4']},
{'id':'expanse','name':'Expanse / heavens','y':32,'h':18,'refs':['Genesis 1:6–8','Psalm 19:1']},
{'id':'land-sea','name':'Earth / land and seas','y':50,'h':23,'refs':['Genesis 1:9–10','Psalm 24:1–2']},
{'id':'deep','name':'Deep / waters below imagery','y':73,'h':12,'refs':['Genesis 1:2','Psalm 104:6']},
{'id':'sheol','name':'Sheol / realm-of-death imagery','y':85,'h':12,'refs':['Psalm 88:3–6','Jonah 2:2','Isaiah 14:9']},
]}

def place_catalog():return PLACES
def temple_model():return TEMPLE
def cosmology_model():return COSMOLOGY
