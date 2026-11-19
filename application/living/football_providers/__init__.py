"""Six documented, independent provider adapters. No credentials in metadata."""
from .apifootball import ApiFootballCom
from .apisports import ApiSports
from .thesportsdb import TheSportsDB
from .highlightly import Highlightly
from .footballdata import FootballData
from .openligadb import OpenLigaDB
ADAPTERS={str(i):cls() for i,cls in enumerate((ApiFootballCom,ApiSports,TheSportsDB,Highlightly,FootballData,OpenLigaDB),1)}
