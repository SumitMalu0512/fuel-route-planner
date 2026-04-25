"""
City geocoder for US locations.
Uses a comprehensive lookup of known US city coordinates,
falling back to state-centroid + deterministic offset for unknown cities.
"""
import hashlib
import math

# Major US cities: (city_lower, state) -> (lat, lng)
# Comprehensive database covering cities that appear in fuel station data
KNOWN_CITIES = {
    # Alabama
    ("birmingham", "AL"): (33.5207, -86.8025),
    ("montgomery", "AL"): (32.3792, -86.3077),
    ("mobile", "AL"): (30.6954, -88.0399),
    ("huntsville", "AL"): (34.7304, -86.5861),
    ("tuscaloosa", "AL"): (33.2098, -87.5692),
    ("dothan", "AL"): (31.2232, -85.3905),
    ("decatur", "AL"): (34.6059, -86.9833),
    ("auburn", "AL"): (32.6099, -85.4808),
    ("shorter", "AL"): (32.3954, -85.9186),
    ("abbeville", "AL"): (31.5716, -85.2505),
    ("calera", "AL"): (33.1029, -86.7536),
    ("loxley", "AL"): (30.6171, -87.7533),
    ("saraland", "AL"): (30.8207, -88.0700),
    ("atmore", "AL"): (31.0240, -87.4939),
    ("greenville", "AL"): (31.8293, -86.6178),
    ("evergreen", "AL"): (31.4335, -86.9572),
    ("york", "AL"): (32.4865, -88.2964),
    ("hope hull", "AL"): (32.2279, -86.3916),
    ("tanner", "AL"): (34.7215, -86.9628),
    ("vance", "AL"): (33.1743, -87.2339),
    # Arizona
    ("phoenix", "AZ"): (33.4484, -112.0740),
    ("tucson", "AZ"): (32.2226, -110.9747),
    ("mesa", "AZ"): (33.4152, -111.8315),
    ("flagstaff", "AZ"): (35.1983, -111.6513),
    ("yuma", "AZ"): (32.6927, -114.6277),
    ("gila bend", "AZ"): (32.9478, -112.7166),
    ("eloy", "AZ"): (32.7559, -111.5540),
    ("kingman", "AZ"): (35.1894, -114.0530),
    ("holbrook", "AZ"): (34.9023, -110.1582),
    ("ehrenberg", "AZ"): (33.6042, -114.5252),
    ("lupton", "AZ"): (35.2992, -109.0700),
    ("tonopah", "AZ"): (33.4531, -112.9578),
    ("willcox", "AZ"): (32.2528, -109.8320),
    ("sanders", "AZ"): (35.2145, -109.3247),
    ("winslow", "AZ"): (35.0242, -110.6974),
    # Arkansas
    ("little rock", "AR"): (34.7465, -92.2896),
    ("fort smith", "AR"): (35.3859, -94.3985),
    ("west memphis", "AR"): (35.1465, -90.1846),
    ("pine bluff", "AR"): (34.2284, -92.0032),
    ("north little rock", "AR"): (34.7695, -92.2671),
    ("russellville", "AR"): (35.2784, -93.1338),
    ("alma", "AR"): (35.4779, -94.2219),
    ("walnut ridge", "AR"): (36.0687, -90.9559),
    ("lonoke", "AR"): (34.7834, -91.8999),
    ("brinkley", "AR"): (34.8879, -91.1946),
    # California
    ("los angeles", "CA"): (34.0522, -118.2437),
    ("san francisco", "CA"): (37.7749, -122.4194),
    ("san diego", "CA"): (32.7157, -117.1611),
    ("sacramento", "CA"): (38.5816, -121.4944),
    ("fresno", "CA"): (36.7378, -119.7871),
    ("bakersfield", "CA"): (35.3733, -119.0187),
    ("ontario", "CA"): (34.0633, -117.6509),
    ("stockton", "CA"): (37.9577, -121.2908),
    ("barstow", "CA"): (34.8958, -117.0173),
    ("needles", "CA"): (34.8480, -114.6142),
    ("coalinga", "CA"): (36.1397, -120.3601),
    ("ripon", "CA"): (37.7413, -121.1244),
    ("lodi", "CA"): (38.1302, -121.2724),
    ("lebec", "CA"): (34.8422, -118.8631),
    ("wheeler ridge", "CA"): (34.9275, -118.9567),
    ("lost hills", "CA"): (35.6166, -119.6943),
    ("santa nella", "CA"): (37.0958, -121.0122),
    ("corning", "CA"): (39.9274, -122.1797),
    ("buttonwillow", "CA"): (35.4005, -119.4690),
    ("truckee", "CA"): (39.3280, -120.1833),
    ("coachella", "CA"): (33.6803, -116.1739),
    ("salinas", "CA"): (36.6777, -121.6555),
    ("redding", "CA"): (40.5865, -122.3917),
    # Colorado
    ("denver", "CO"): (39.7392, -104.9903),
    ("colorado springs", "CO"): (38.8339, -104.8214),
    ("pueblo", "CO"): (38.2544, -104.6091),
    ("fort collins", "CO"): (40.5853, -105.0844),
    ("grand junction", "CO"): (39.0639, -108.5506),
    ("montrose", "CO"): (38.4783, -107.8762),
    ("limon", "CO"): (39.2639, -103.6922),
    ("dumont", "CO"): (39.7525, -105.6114),
    ("atwood", "CO"): (40.5344, -102.2168),
    ("burlington", "CO"): (39.3058, -102.2693),
    ("brush", "CO"): (40.2586, -103.6333),
    # Connecticut
    ("hartford", "CT"): (41.7658, -72.6734),
    ("new haven", "CT"): (41.3083, -72.9279),
    ("bridgeport", "CT"): (41.1865, -73.1952),
    ("milford", "CT"): (41.2223, -73.0565),
    # Delaware
    ("wilmington", "DE"): (39.7391, -75.5398),
    ("dover", "DE"): (39.1582, -75.5244),
    ("new castle", "DE"): (39.6621, -75.5666),
    ("laurel", "DE"): (38.5565, -75.5713),
    # Florida
    ("jacksonville", "FL"): (30.3322, -81.6557),
    ("miami", "FL"): (25.7617, -80.1918),
    ("tampa", "FL"): (27.9506, -82.4572),
    ("orlando", "FL"): (28.5383, -81.3792),
    ("ocala", "FL"): (29.1872, -82.1401),
    ("gainesville", "FL"): (29.6516, -82.3248),
    ("tallahassee", "FL"): (30.4383, -84.2807),
    ("pensacola", "FL"): (30.4213, -87.2169),
    ("fort lauderdale", "FL"): (26.1224, -80.1373),
    ("daytona beach", "FL"): (29.2108, -81.0228),
    ("fort myers", "FL"): (26.6406, -81.8723),
    ("ellenton", "FL"): (27.5225, -82.5276),
    ("wildwood", "FL"): (28.7653, -82.0401),
    ("port st. lucie", "FL"): (27.2730, -80.3582),
    ("white springs", "FL"): (30.3299, -82.7593),
    ("baldwin", "FL"): (30.3027, -81.9748),
    # Georgia
    ("atlanta", "GA"): (33.7490, -84.3880),
    ("savannah", "GA"): (32.0809, -81.0912),
    ("augusta", "GA"): (33.4735, -81.9748),
    ("macon", "GA"): (32.8407, -83.6324),
    ("columbus", "GA"): (32.4610, -84.9877),
    ("albany", "GA"): (31.5785, -84.1557),
    ("tifton", "GA"): (31.4505, -83.5085),
    ("cordele", "GA"): (31.9635, -83.7746),
    ("adel", "GA"): (31.1374, -83.4243),
    ("perry", "GA"): (32.4585, -83.7316),
    ("commerce", "GA"): (34.2037, -83.4571),
    ("calhoun", "GA"): (34.5026, -84.9513),
    ("crawfordville", "GA"): (33.5540, -82.8954),
    ("adairsville", "GA"): (34.3687, -84.9341),
    # Idaho
    ("boise", "ID"): (43.6150, -116.2023),
    ("idaho falls", "ID"): (43.4917, -112.0339),
    ("pocatello", "ID"): (42.8713, -112.4455),
    ("twin falls", "ID"): (42.5558, -114.4601),
    ("nampa", "ID"): (43.5407, -116.5635),
    ("caldwell", "ID"): (43.6629, -116.6874),
    ("hammett", "ID"): (42.9502, -115.4688),
    ("inkom", "ID"): (42.7966, -112.2519),
    # Illinois
    ("chicago", "IL"): (41.8781, -87.6298),
    ("springfield", "IL"): (39.7817, -89.6501),
    ("rockford", "IL"): (42.2711, -89.0940),
    ("effingham", "IL"): (39.1200, -88.5434),
    ("bloomington", "IL"): (40.4842, -88.9937),
    ("champaign", "IL"): (40.1164, -88.2434),
    ("joliet", "IL"): (41.5250, -88.0817),
    ("mount vernon", "IL"): (38.3173, -88.9031),
    ("channahon", "IL"): (41.4450, -88.2170),
    ("peru", "IL"): (41.3275, -89.1290),
    ("kankakee", "IL"): (41.1200, -87.8612),
    ("east saint louis", "IL"): (38.6245, -90.1510),
    ("east st. louis", "IL"): (38.6245, -90.1510),
    ("troy", "IL"): (38.7292, -89.8834),
    ("olney", "IL"): (38.7309, -88.0853),
    ("gilman", "IL"): (40.7667, -87.9923),
    ("atkinson", "IL"): (41.4169, -89.9987),
    ("monee", "IL"): (41.4203, -87.7417),
    ("bensenville", "IL"): (41.9550, -87.9401),
    ("alsip", "IL"): (41.6689, -87.7384),
    ("marshall", "IL"): (39.3917, -87.6936),
    ("oakwood", "IL"): (40.1128, -87.7781),
    ("hampshire", "IL"): (42.0978, -88.5306),
    ("lombard", "IL"): (41.8803, -88.0079),
    ("lincoln", "IL"): (40.1486, -89.3648),
    ("pontiac", "IL"): (40.8806, -88.6298),
    ("walcott", "IL"): (41.5867, -90.7679),
    ("normal", "IL"): (40.5142, -88.9906),
    # Indiana
    ("indianapolis", "IN"): (39.7684, -86.1581),
    ("fort wayne", "IN"): (41.0793, -85.1394),
    ("south bend", "IN"): (41.6764, -86.2520),
    ("evansville", "IN"): (37.9716, -87.5711),
    ("gary", "IN"): (41.5934, -87.3465),
    ("seymour", "IN"): (38.9592, -85.8902),
    ("lake station", "IN"): (41.5753, -87.2606),
    ("hebron", "IN"): (41.3186, -87.2001),
    ("daleville", "IN"): (40.1214, -85.5569),
    ("remington", "IN"): (40.7600, -87.1509),
    ("whiteland", "IN"): (39.5503, -86.0797),
    ("edinburgh", "IN"): (39.3522, -85.9666),
    # Iowa
    ("des moines", "IA"): (41.5868, -93.6250),
    ("cedar rapids", "IA"): (41.9779, -91.6656),
    ("davenport", "IA"): (41.5236, -90.5776),
    ("council bluffs", "IA"): (41.2619, -95.8608),
    ("clear lake", "IA"): (43.1380, -93.3797),
    ("stuart", "IA"): (41.5033, -94.3186),
    ("latimer", "IA"): (42.7619, -93.3697),
    ("vinton", "IA"): (42.1686, -92.0235),
    ("williamsburg", "IA"): (41.6611, -92.0088),
    ("walcott", "IA"): (41.5867, -90.7679),
    ("grinnell", "IA"): (41.7433, -92.7224),
    # Kansas
    ("wichita", "KS"): (37.6872, -97.3301),
    ("topeka", "KS"): (39.0473, -95.6752),
    ("kansas city", "KS"): (39.1141, -94.6275),
    ("salina", "KS"): (38.8403, -97.6114),
    ("abilene", "KS"): (38.9172, -97.2137),
    ("colby", "KS"): (39.3958, -101.0522),
    ("hays", "KS"): (38.8792, -99.3268),
    ("emporia", "KS"): (38.4039, -96.1817),
    ("junction city", "KS"): (39.0286, -96.8314),
    # Kentucky
    ("louisville", "KY"): (38.2527, -85.7585),
    ("lexington", "KY"): (38.0406, -84.5037),
    ("bowling green", "KY"): (36.9685, -86.4808),
    ("henderson", "KY"): (37.8362, -87.5900),
    ("georgetown", "KY"): (38.2098, -84.5588),
    ("corbin", "KY"): (36.9487, -84.0968),
    ("london", "KY"): (37.1290, -84.0833),
    ("oak grove", "KY"): (36.6656, -87.4428),
    ("walton", "KY"): (38.8757, -84.6102),
    # Louisiana
    ("new orleans", "LA"): (29.9511, -90.0715),
    ("baton rouge", "LA"): (30.4515, -91.1871),
    ("shreveport", "LA"): (32.5252, -93.7502),
    ("port allen", "LA"): (30.4521, -91.2101),
    ("denham springs", "LA"): (30.4866, -90.9568),
    ("scott", "LA"): (30.2360, -92.0943),
    ("slidell", "LA"): (30.2752, -89.7812),
    ("lafayette", "LA"): (30.2241, -92.0198),
    ("breaux bridge", "LA"): (30.2735, -91.8993),
    # Maine
    ("portland", "ME"): (43.6591, -70.2568),
    ("bangor", "ME"): (44.8012, -68.7778),
    ("houlton", "ME"): (46.1261, -67.8403),
    # Maryland
    ("baltimore", "MD"): (39.2904, -76.6122),
    ("aberdeen", "MD"): (39.5096, -76.1644),
    ("jessup", "MD"): (39.1484, -76.7750),
    ("hagerstown", "MD"): (39.6418, -77.7200),
    ("accident", "MD"): (39.6270, -79.3217),
    # Massachusetts
    ("boston", "MA"): (42.3601, -71.0589),
    ("springfield", "MA"): (42.1015, -72.5898),
    ("worcester", "MA"): (42.2626, -71.8023),
    ("adams", "MA"): (42.6234, -73.1176),
    ("seekonk", "MA"): (41.8084, -71.3370),
    # Michigan
    ("detroit", "MI"): (42.3314, -83.0458),
    ("grand rapids", "MI"): (42.9634, -85.6681),
    ("lansing", "MI"): (42.7325, -84.5555),
    ("monroe", "MI"): (41.9164, -83.3977),
    ("bridgeport", "MI"): (43.3595, -83.8816),
    ("marshall", "MI"): (42.2723, -84.9633),
    ("dexter", "MI"): (42.3381, -83.8886),
    ("saginaw", "MI"): (43.4195, -83.9508),
    ("battle creek", "MI"): (42.3212, -85.1797),
    ("jackson", "MI"): (42.2459, -84.4013),
    ("ann arbor", "MI"): (42.2808, -83.7430),
    ("holland", "MI"): (42.7876, -86.1089),
    # Minnesota
    ("minneapolis", "MN"): (44.9778, -93.2650),
    ("st. paul", "MN"): (44.9537, -93.0900),
    ("duluth", "MN"): (46.7867, -92.1005),
    ("rochester", "MN"): (44.0121, -92.4802),
    ("albert lea", "MN"): (43.6480, -93.3683),
    ("jackson", "MN"): (43.6208, -95.0334),
    ("adrian", "MN"): (43.6319, -95.9329),
    ("rogers", "MN"): (45.1886, -93.5530),
    # Mississippi
    ("jackson", "MS"): (32.2988, -90.1848),
    ("meridian", "MS"): (32.3643, -88.7037),
    ("hattiesburg", "MS"): (31.3271, -89.2903),
    ("vicksburg", "MS"): (32.3526, -90.8779),
    ("corinth", "MS"): (34.9343, -88.5223),
    # Missouri
    ("kansas city", "MO"): (39.0997, -94.5786),
    ("st. louis", "MO"): (38.6270, -90.1994),
    ("springfield", "MO"): (37.2090, -93.2923),
    ("joplin", "MO"): (37.0842, -94.5133),
    ("columbia", "MO"): (38.9517, -92.3341),
    ("saint robert", "MO"): (37.8281, -92.1757),
    ("oak grove", "MO"): (38.9628, -94.1297),
    ("kingdom city", "MO"): (38.9458, -91.9346),
    # Montana
    ("billings", "MT"): (45.7833, -108.5007),
    ("missoula", "MT"): (46.8721, -113.9940),
    ("great falls", "MT"): (47.5002, -111.3008),
    ("butte", "MT"): (46.0038, -112.5348),
    # Nebraska
    ("omaha", "NE"): (41.2565, -95.9345),
    ("lincoln", "NE"): (40.8136, -96.7026),
    ("grand island", "NE"): (40.9264, -98.3420),
    ("gothenburg", "NE"): (40.9297, -100.1601),
    ("north platte", "NE"): (41.1240, -100.7654),
    ("kearney", "NE"): (40.6993, -99.0832),
    ("york", "NE"): (40.8681, -97.5920),
    # Nevada
    ("las vegas", "NV"): (36.1699, -115.1398),
    ("reno", "NV"): (39.5296, -119.8138),
    ("sparks", "NV"): (39.5349, -119.7527),
    ("fernley", "NV"): (39.6080, -119.2518),
    ("lovelock", "NV"): (40.1793, -118.4734),
    ("wells", "NV"): (41.1099, -114.9644),
    ("west wendover", "NV"): (40.7391, -114.0734),
    # New Hampshire
    ("concord", "NH"): (43.2081, -71.5376),
    ("hooksett", "NH"): (43.0970, -71.4651),
    # New Jersey
    ("newark", "NJ"): (40.7357, -74.1724),
    ("columbia", "NJ"): (40.9243, -75.0885),
    ("bordentown", "NJ"): (40.1465, -74.7118),
    ("carneys point", "NJ"): (39.7126, -75.4702),
    ("bloomsbury", "NJ"): (40.6526, -75.0835),
    # New Mexico
    ("albuquerque", "NM"): (35.0844, -106.6504),
    ("las cruces", "NM"): (32.3199, -106.7637),
    ("santa fe", "NM"): (35.6870, -105.9378),
    ("gallup", "NM"): (35.5281, -108.7426),
    ("tucumcari", "NM"): (35.1720, -103.7250),
    ("lordsburg", "NM"): (32.3504, -108.7093),
    ("deming", "NM"): (32.2687, -107.7586),
    ("las vegas", "NM"): (35.5942, -105.2239),
    # New York
    ("new york", "NY"): (40.7128, -74.0060),
    ("buffalo", "NY"): (42.8864, -78.8784),
    ("syracuse", "NY"): (43.0481, -76.1474),
    ("albany", "NY"): (42.6526, -73.7562),
    ("rochester", "NY"): (43.1566, -77.6088),
    ("utica", "NY"): (43.1009, -75.2327),
    ("binghamton", "NY"): (42.0987, -75.9180),
    # North Carolina
    ("charlotte", "NC"): (35.2271, -80.8431),
    ("raleigh", "NC"): (35.7796, -78.6382),
    ("greensboro", "NC"): (36.0726, -79.7920),
    ("durham", "NC"): (35.9940, -78.8986),
    ("fayetteville", "NC"): (35.0527, -78.8784),
    ("conover", "NC"): (35.7068, -81.2187),
    ("pleasant hill", "NC"): (36.5171, -79.4837),
    ("lumberton", "NC"): (34.6182, -79.0086),
    ("smithfield", "NC"): (35.5085, -78.3394),
    # North Dakota
    ("bismarck", "ND"): (46.8083, -100.7837),
    ("fargo", "ND"): (46.8772, -96.7898),
    ("sterling", "ND"): (46.8267, -100.2812),
    # Ohio
    ("columbus", "OH"): (39.9612, -82.9988),
    ("cleveland", "OH"): (41.4993, -81.6944),
    ("cincinnati", "OH"): (39.1031, -84.5120),
    ("dayton", "OH"): (39.7589, -84.1916),
    ("toledo", "OH"): (41.6528, -83.5379),
    ("akron", "OH"): (41.0814, -81.5190),
    ("canton", "OH"): (40.7990, -81.3784),
    ("lodi", "OH"): (41.0334, -82.0118),
    ("north jackson", "OH"): (41.0959, -80.8620),
    ("milan", "OH"): (41.2978, -82.6049),
    # Oklahoma
    ("oklahoma city", "OK"): (35.4676, -97.5164),
    ("tulsa", "OK"): (36.1540, -95.9928),
    ("big cabin", "OK"): (36.5373, -95.2192),
    ("ada", "OK"): (34.7745, -96.6783),
    ("afton", "OK"): (36.6937, -94.9631),
    ("red rock", "OK"): (36.4573, -97.1756),
    ("sallisaw", "OK"): (35.4601, -94.7874),
    ("sayre", "OK"): (35.2912, -99.6401),
    ("calumet", "OK"): (35.6075, -98.1143),
    ("el reno", "OK"): (35.5323, -97.9551),
    # Oregon
    ("portland", "OR"): (45.5152, -122.6784),
    ("eugene", "OR"): (44.0521, -123.0868),
    ("salem", "OR"): (44.9429, -123.0351),
    ("medford", "OR"): (42.3265, -122.8756),
    ("bend", "OR"): (44.0582, -121.3153),
    ("troutdale", "OR"): (45.5393, -122.3878),
    ("biggs junction", "OR"): (45.6215, -120.8368),
    # Pennsylvania
    ("philadelphia", "PA"): (39.9526, -75.1652),
    ("pittsburgh", "PA"): (40.4406, -79.9959),
    ("harrisburg", "PA"): (40.2732, -76.8867),
    ("allentown", "PA"): (40.6023, -75.4714),
    ("erie", "PA"): (42.1292, -80.0851),
    ("scranton", "PA"): (41.4090, -75.6624),
    ("carlisle", "PA"): (40.2015, -77.1886),
    ("breezewood", "PA"): (39.9987, -78.2392),
    ("greencastle", "PA"): (39.7904, -77.7272),
    ("clearfield", "PA"): (41.0276, -78.4392),
    # Rhode Island
    ("providence", "RI"): (41.8240, -71.4128),
    # South Carolina
    ("columbia", "SC"): (34.0007, -81.0348),
    ("charleston", "SC"): (32.7765, -79.9311),
    ("greenville", "SC"): (34.8526, -82.3940),
    ("abbeville", "SC"): (34.1782, -82.3790),
    ("florence", "SC"): (34.1954, -79.7626),
    ("dillon", "SC"): (34.4168, -79.3712),
    ("santee", "SC"): (33.4932, -80.4085),
    ("hardeeville", "SC"): (32.2816, -81.0804),
    # South Dakota
    ("sioux falls", "SD"): (43.5446, -96.7311),
    ("rapid city", "SD"): (44.0805, -103.2310),
    ("aberdeen", "SD"): (45.4647, -98.4865),
    ("mitchell", "SD"): (43.7094, -98.0298),
    ("murdo", "SD"): (43.8867, -100.7123),
    # Tennessee
    ("nashville", "TN"): (36.1627, -86.7816),
    ("memphis", "TN"): (35.1495, -90.0490),
    ("knoxville", "TN"): (35.9606, -83.9207),
    ("chattanooga", "TN"): (35.0456, -85.3097),
    ("cookeville", "TN"): (36.1628, -85.5016),
    ("lebanon", "TN"): (36.2086, -86.2911),
    ("crossville", "TN"): (35.9489, -85.0269),
    ("hurricane mills", "TN"): (35.9553, -87.7828),
    # Texas
    ("houston", "TX"): (29.7604, -95.3698),
    ("san antonio", "TX"): (29.4241, -98.4936),
    ("dallas", "TX"): (32.7767, -96.7970),
    ("fort worth", "TX"): (32.7555, -97.3308),
    ("austin", "TX"): (30.2672, -97.7431),
    ("el paso", "TX"): (31.7619, -106.4850),
    ("lubbock", "TX"): (33.5779, -101.8552),
    ("amarillo", "TX"): (35.2220, -101.8313),
    ("laredo", "TX"): (27.5036, -99.5076),
    ("midland", "TX"): (31.9973, -102.0779),
    ("odessa", "TX"): (31.8457, -102.3676),
    ("abilene", "TX"): (32.4487, -99.7331),
    ("pecos", "TX"): (31.4229, -103.4932),
    ("waco", "TX"): (31.5493, -97.1467),
    ("canton", "TX"): (32.5565, -95.8633),
    ("nacogdoches", "TX"): (31.6035, -94.6555),
    ("jarrell", "TX"): (30.8224, -97.6042),
    ("abbott", "TX"): (31.8838, -97.0739),
    ("seguin", "TX"): (29.5688, -97.9647),
    ("terrell", "TX"): (32.7360, -96.2753),
    ("weatherford", "TX"): (32.7593, -97.7973),
    ("baytown", "TX"): (29.7355, -94.9774),
    # Utah
    ("salt lake city", "UT"): (40.7608, -111.8910),
    ("provo", "UT"): (40.2338, -111.6585),
    ("ogden", "UT"): (41.2230, -111.9738),
    ("st. george", "UT"): (37.0965, -113.5684),
    ("perry", "UT"): (41.4649, -112.0352),
    ("scipio", "UT"): (39.2447, -112.1008),
    # Vermont
    ("burlington", "VT"): (44.4759, -73.2121),
    ("rutland", "VT"): (43.6106, -72.9726),
    # Virginia
    ("richmond", "VA"): (37.5407, -77.4360),
    ("virginia beach", "VA"): (36.8529, -75.9780),
    ("norfolk", "VA"): (36.8508, -76.2859),
    ("mount jackson", "VA"): (38.7460, -78.6425),
    ("wytheville", "VA"): (36.9485, -81.0848),
    ("staunton", "VA"): (38.1496, -79.0717),
    ("winchester", "VA"): (39.1857, -78.1633),
    ("bristol", "VA"): (36.5960, -82.1887),
    ("stephens city", "VA"): (39.0835, -78.2186),
    # Washington
    ("seattle", "WA"): (47.6062, -122.3321),
    ("spokane", "WA"): (47.6588, -117.4260),
    ("tacoma", "WA"): (47.2529, -122.4443),
    ("ellensburg", "WA"): (46.9965, -120.5478),
    ("cle elum", "WA"): (47.1951, -120.9393),
    ("centralia", "WA"): (46.7162, -122.9543),
    ("north bend", "WA"): (47.4957, -121.7868),
    # West Virginia
    ("charleston", "WV"): (38.3498, -81.6326),
    ("princeton", "WV"): (37.3665, -81.1026),
    ("nitro", "WV"): (38.4148, -81.8421),
    ("falling waters", "WV"): (39.5854, -77.8483),
    # Wisconsin
    ("milwaukee", "WI"): (43.0389, -87.9065),
    ("madison", "WI"): (43.0731, -89.4012),
    ("green bay", "WI"): (44.5133, -88.0133),
    ("tomah", "WI"): (43.9780, -90.5040),
    ("abbotsford", "WI"): (44.9469, -90.3160),
    ("adams", "WI"): (43.9566, -89.8151),
    # Wyoming
    ("cheyenne", "WY"): (41.1400, -104.8202),
    ("casper", "WY"): (42.8666, -106.3131),
    ("laramie", "WY"): (41.3114, -105.5911),
    ("moorcroft", "WY"): (44.2636, -104.9502),
    ("rawlins", "WY"): (41.7911, -107.2387),
    ("rock springs", "WY"): (41.5875, -109.2029),
    ("evanston", "WY"): (41.2683, -110.9632),
    ("sheridan", "WY"): (44.7972, -106.9562),
}

# State centroids for fallback
STATE_CENTROIDS = {
    'AL': (32.806671, -86.791130), 'AK': (61.370716, -152.404419),
    'AZ': (33.729759, -111.431221), 'AR': (34.969704, -92.373123),
    'CA': (36.116203, -119.681564), 'CO': (39.059811, -105.311104),
    'CT': (41.597782, -72.755371), 'DE': (39.318523, -75.507141),
    'FL': (27.766279, -81.686783), 'GA': (33.040619, -83.643074),
    'HI': (21.094318, -157.498337), 'ID': (44.240459, -114.478828),
    'IL': (40.349457, -88.986137), 'IN': (39.849426, -86.258278),
    'IA': (42.011539, -93.210526), 'KS': (38.526600, -96.726486),
    'KY': (37.668140, -84.670067), 'LA': (31.169546, -91.867805),
    'ME': (44.693947, -69.381927), 'MD': (39.063946, -76.802101),
    'MA': (42.230171, -71.530106), 'MI': (43.326618, -84.536095),
    'MN': (45.694454, -93.900192), 'MS': (32.741646, -89.678696),
    'MO': (38.456085, -92.288368), 'MT': (46.921925, -110.454353),
    'NE': (41.125370, -98.268082), 'NV': (38.313515, -117.055374),
    'NH': (43.452492, -71.563896), 'NJ': (40.298904, -74.521011),
    'NM': (34.840515, -106.248482), 'NY': (42.165726, -74.948051),
    'NC': (35.630066, -79.806419), 'ND': (47.528912, -99.784012),
    'OH': (40.388783, -82.764915), 'OK': (35.565342, -96.928917),
    'OR': (44.572021, -122.070938), 'PA': (40.590752, -77.209755),
    'RI': (41.680893, -71.511780), 'SC': (33.856892, -80.945007),
    'SD': (44.299782, -99.438828), 'TN': (35.747845, -86.692345),
    'TX': (31.054487, -97.563461), 'UT': (40.150032, -111.862434),
    'VT': (44.045876, -72.710686), 'VA': (37.769337, -78.169968),
    'WA': (47.400902, -121.490494), 'WV': (38.491226, -80.954453),
    'WI': (44.268543, -89.616508), 'WY': (42.755966, -107.302490),
}

US_STATES = set(STATE_CENTROIDS.keys())


def geocode_city(city: str, state: str) -> tuple:
    """
    Get approximate coordinates for a US city.
    Returns (latitude, longitude) or (None, None) if state unknown.
    """
    if state not in US_STATES:
        return None, None

    # Try exact match (case-insensitive)
    key = (city.lower().strip(), state)
    if key in KNOWN_CITIES:
        return KNOWN_CITIES[key]

    # Try without trailing spaces
    key2 = (city.lower().strip(), state.strip())
    if key2 in KNOWN_CITIES:
        return KNOWN_CITIES[key2]

    # Fallback: deterministic placement within state bounds using city name hash
    h = hashlib.md5(f"{city.lower().strip()}_{state}".encode()).hexdigest()
    lat_frac = int(h[:8], 16) / 0xFFFFFFFF
    lng_frac = int(h[8:16], 16) / 0xFFFFFFFF

    center_lat, center_lng = STATE_CENTROIDS[state]
    # Place within ~1 degree of state centroid with hash-based offset
    lat = center_lat + (lat_frac - 0.5) * 2.0
    lng = center_lng + (lng_frac - 0.5) * 2.0

    return round(lat, 4), round(lng, 4)


def geocode_location(location_str: str) -> tuple:
    """
    Geocode a free-text US location string like 'New York, NY' or 'Los Angeles, CA'.
    Returns (latitude, longitude, city, state).
    """
    parts = [p.strip() for p in location_str.split(',')]
    if len(parts) < 2:
        # Try to match as a known city
        city = parts[0].strip()
        for state in US_STATES:
            if (city.lower(), state) in KNOWN_CITIES:
                lat, lng = KNOWN_CITIES[(city.lower(), state)]
                return lat, lng, city, state
        return None, None, None, None

    city = parts[0].strip()
    state = parts[-1].strip().upper()

    # Handle full state names
    state_name_map = {
        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
        'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
        'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
        'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
        'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
        'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN',
        'MISSISSIPPI': 'MS', 'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE',
        'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ',
        'NEW MEXICO': 'NM', 'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC',
        'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK', 'OREGON': 'OR',
        'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
        'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
        'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA',
        'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY',
    }
    if state in state_name_map:
        state = state_name_map[state]

    if state not in US_STATES:
        return None, None, None, None

    lat, lng = geocode_city(city, state)
    return lat, lng, city, state
