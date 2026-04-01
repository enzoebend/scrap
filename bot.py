#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
+------------------------------------------------------------------+
| CAR HUNTER PRO - Sportives Allemandes Stage 1                    |
| Mobile.de | AutoScout24 | HeyCar | LeBonCoin                     |
| 25 profils | DE | 5k-22.5k EUR | <130k km | 2014+                |
| BMW 1/2/3/4/5 M | Audi A3/A4/A5/S/RS | VW | Mercedes C/E/A      |
+------------------------------------------------------------------+
"""
import re
import time
import random
import logging
import hashlib
import sqlite3
import requests
import traceback
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode
from bs4 import BeautifulSoup

# ------------------------------------------------------------------
# CONFIG — seule section à modifier
# ------------------------------------------------------------------
CONFIG = {
    "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/1488788430925074516/B3YQWKbrWdJtKZ-Mr14hgz7M7slRGxNYo5xUD_414Gi4CKz5pEmORQ1HC4PBNrv5kBJ1",
    "PRICE_MIN": 5_000,       # € minimum (filtre épaves)
    "PRICE_MAX": 22_500,      # € maximum absolu
    "PRICE_TARGET": 15_000,   # € budget cible (bonus scoring)
    "DEAL_SCORE_MIN": 60,     # score /100 pour déclencher une notif
    "PRICE_BELOW_MARKET": 0.85,  # annonce < 85% du prix marché = deal
    "CHECK_INTERVAL": 240,    # secondes entre cycles (4 min)
    "REQUEST_DELAY": (3.0, 7.0),  # délai anti-ban entre requêtes
    "DB_PATH": "car_hunter_de.db",
    "LOG_PATH": "car_hunter_de.log",
    "PROXIES": [],  # ex: ["http://user:pass@ip:port"]
}

# ------------------------------------------------------------------
# PROFILS MODÈLES
# ------------------------------------------------------------------
MODEL_PROFILES = {
    # ---------------------------------------------------
    # BMW — Série 1 / 2 / 3 / 4 / 5 + M
    # ---------------------------------------------------
    "bmw_120_230": {
        "label": "BMW 120i / 125i / 230i (B48)", "emoji": "🚗",
        "make": "bmw", "model_id": "1er",
        "keywords": ["120i", "125i", "230i", "bmw 1er", "bmw 118i", "f40", "f22", "b48"],
        "engine_kw": ["b48", "zf8", "m sport", "steptronic", "f22", "f40"],
        "min_year": 2016, "min_power": 136, "market_base": 19_000,
        "stage1_note": "Stage 1 B48 → 230–250 ch, ZF8 très robuste et reprogrammable",
        "color": 0x2980B9,
    },
    "bmw_m135i": {
        "label": "BMW M135i / M140i N55 (F20/F21)", "emoji": "🔥",
        "make": "bmw", "model_id": "1er",
        "keywords": ["m135i", "m140i", "m135", "m140", "n55", "6 zylinder"],
        "engine_kw": ["n55", "m135", "m140", "xdrive", "6 zyl"],
        "min_year": 2013, "min_power": 315, "market_base": 22_000,
        "stage1_note": "Stage 1 N55 → 380–420 ch, sensations de M3 pour 3x moins cher",
        "color": 0xE67E22,
    },
    "bmw_320_330": {
        "label": "BMW 320i / 330i Série 3 (B46/B48)", "emoji": "🚗",
        "make": "bmw", "model_id": "3er",
        "keywords": ["320i", "330i", "serie 3", "bmw 3", "f30", "g20", "320d sport", "330e"],
        "engine_kw": ["b46", "b48", "320i", "330i", "m sport", "xdrive", "zf8"],
        "min_year": 2016, "min_power": 156, "market_base": 22_500,
        "stage1_note": "Stage 1 B48 → 270–300 ch, berline premium polyvalente et fiable",
        "color": 0x1F618D,
    },
    "bmw_m340": {
        "label": "BMW 340i / M340i (B58 — G20/F30)", "emoji": "⚡",
        "make": "bmw", "model_id": "3er",
        "keywords": ["340i", "m340i", "b58", "m340", "335i", "335", "f30 340"],
        "engine_kw": ["b58", "340i", "m340", "xdrive", "6 cylindres", "zf8"],
        "min_year": 2015, "min_power": 300, "market_base": 26_000,
        "stage1_note": "Stage 1 B58 → 400–450 ch, moteur légendaire, rival M3 budget",
        "color": 0x154360,
    },
    "bmw_430_440": {
        "label": "BMW 430i / 440i Série 4 Coupé (F32/G22)", "emoji": "🏎️",
        "make": "bmw", "model_id": "4er",
        "keywords": ["430i", "440i", "serie 4", "bmw 4", "f32", "g22", "420i", "430", "coupe bmw"],
        "engine_kw": ["430i", "440i", "b48", "b58", "m sport", "xdrive"],
        "min_year": 2014, "min_power": 184, "market_base": 24_000,
        "stage1_note": "Stage 1 B58 sur 440i → 400 ch, coupé 4 pl élégant à prix réduit",
        "color": 0x1A5276,
    },
    "bmw_520_530": {
        "label": "BMW 520i / 530i Série 5 (G30)", "emoji": "🚗",
        "make": "bmw", "model_id": "5er",
        "keywords": ["520i", "530i", "serie 5", "bmw 5", "g30", "f10", "520", "530"],
        "engine_kw": ["520i", "530i", "b46", "b48", "m sport", "xdrive", "zf8"],
        "min_year": 2016, "min_power": 170, "market_base": 25_000,
        "stage1_note": "Stage 1 → 250–310 ch, grand confort + puissance, idéal GT",
        "color": 0x117A65,
    },
    "bmw_m2_m3_m4": {
        "label": "BMW M2 / M3 / M4 (S55/S58)", "emoji": "🏁",
        "make": "bmw", "model_id": "m2",
        "keywords": ["bmw m2", "bmw m3", "bmw m4", "s55", "s58", "m2 competition", "m3 f80", "m4 f82"],
        "engine_kw": ["s55", "s58", "m2", "m3", "m4", "competition", "dct", "m xdrive"],
        "min_year": 2015, "min_power": 370, "market_base": 35_000,
        "stage1_note": "Stage 1 S55/S58 → 480–520 ch, holy grail du tuning BMW",
        "color": 0x922B21,
    },
    # ---------------------------------------------------
    # AUDI — A3 / A4 / A5 / S / RS
    # ---------------------------------------------------
    "audi_a3_s3": {
        "label": "Audi A3 2.0 TFSI / S3 (8V/8Y)", "emoji": "🚗",
        "make": "audi", "model_id": "a3",
        "keywords": ["audi a3 2.0", "a3 tfsi", "s3 8v", "s3 8y", "a3 s line", "a3 190", "a3 220", "a3 sportback"],
        "engine_kw": ["2.0 tfsi", "s3", "quattro", "s tronic", "ea888"],
        "min_year": 2016, "min_power": 180, "market_base": 21_000,
        "stage1_note": "Stage 1 → 280 ch sur 190ch / 380 ch sur S3 310ch + quattro",
        "color": 0x8E44AD,
    },
    "audi_a4_s4": {
        "label": "Audi A4 2.0 TFSI / S4 (B9)", "emoji": "🚗",
        "make": "audi", "model_id": "a4",
        "keywords": ["audi a4 2.0", "a4 tfsi", "a4 s line", "s4 b9", "a4 190", "a4 252", "a4 avant"],
        "engine_kw": ["2.0 tfsi", "s4", "quattro", "s tronic", "b9", "3.0 tfsi"],
        "min_year": 2016, "min_power": 150, "market_base": 23_000,
        "stage1_note": "Stage 1 → 280 ch sur 190ch, limousine polyvalente et fiable",
        "color": 0x6C3483,
    },
    "audi_a5_s5": {
        "label": "Audi A5 2.0 TFSI / S5 Coupé (B9)", "emoji": "🚗",
        "make": "audi", "model_id": "a5",
        "keywords": ["audi a5 2.0", "a5 tfsi", "a5 s line", "s5 b9", "a5 190", "a5 252", "a5 coupe", "a5 sportback"],
        "engine_kw": ["2.0 tfsi", "s5", "quattro", "s tronic", "3.0 tfsi"],
        "min_year": 2016, "min_power": 150, "market_base": 25_000,
        "stage1_note": "Stage 1 A5 → 280 ch, coupé premium élégant, concurrent Série 4",
        "color": 0x7D3C98,
    },
    "audi_rs3_rs4": {
        "label": "Audi RS3 / RS4 / RS5 (EA855/DKZC)", "emoji": "🔥",
        "make": "audi", "model_id": "rs3",
        "keywords": ["audi rs3", "audi rs4", "audi rs5", "rs3 sportback", "rs4 avant", "rs5 coupe", "2.5 tfsi", "rs 3", "rs 4"],
        "engine_kw": ["rs3", "rs4", "rs5", "2.5 tfsi", "quattro", "s tronic", "ea855"],
        "min_year": 2015, "min_power": 340, "market_base": 34_000,
        "stage1_note": "Stage 1 RS3 2.5T → 460 ch, 5 cylindres culte, son unique",
        "color": 0xC0392B,
    },
    # ---------------------------------------------------
    # MERCEDES — Classe A / C / E / CLA / GLA
    # ---------------------------------------------------
    "mercedes_a250": {
        "label": "Mercedes A250 / A35 AMG (M260/M260E)", "emoji": "🚗",
        "make": "mercedes", "model_id": "a-klasse",
        "keywords": ["a250", "a 250", "a35", "a35 amg", "m260", "amg line a", "a class"],
        "engine_kw": ["m260", "a250", "a35", "amg", "7g-dct", "4matic"],
        "min_year": 2018, "min_power": 218, "market_base": 24_000,
        "stage1_note": "Stage 1 M260 → 300 ch / A35 AMG → 380 ch, best in class feeling",
        "color": 0x1ABC9C,
    },
    "mercedes_cla_gla": {
        "label": "Mercedes CLA 250 / GLA 250 (M260)", "emoji": "🚗",
        "make": "mercedes", "model_id": "cla",
        "keywords": ["cla 250", "cla250", "gla 250", "gla250", "cla amg line", "gla amg", "cla 35"],
        "engine_kw": ["m260", "cla250", "gla250", "amg", "7g-dct", "4matic"],
        "min_year": 2018, "min_power": 218, "market_base": 25_000,
        "stage1_note": "Stage 1 → 300 ch, look coupé ou SUV compact selon goût",
        "color": 0x0E6655,
    },
    "mercedes_c250_c300": {
        "label": "Mercedes Classe C 200/250/300 (W205/W206)", "emoji": "🚗",
        "make": "mercedes", "model_id": "c-klasse",
        "keywords": ["c200", "c250", "c300", "classe c", "w205", "w206", "c amg line", "c 250"],
        "engine_kw": ["m264", "m270", "c200", "c250", "c300", "amg line", "9g-tronic"],
        "min_year": 2015, "min_power": 156, "market_base": 22_000,
        "stage1_note": "Stage 1 M264 → 260 ch, berline premium à prix Série 3",
        "color": 0x148F77,
    },
    "mercedes_c43_amg": {
        "label": "Mercedes C43 / C63 AMG (M276/M177)", "emoji": "🔥",
        "make": "mercedes", "model_id": "c-klasse",
        "keywords": ["c43 amg", "c63 amg", "c43", "c63", "amg c43", "amg c63", "m177", "m276"],
        "engine_kw": ["c43", "c63", "m177", "m276", "amg", "9g-tronic", "speedshift"],
        "min_year": 2015, "min_power": 367, "market_base": 32_000,
        "stage1_note": "Stage 1 M177 (C63) → 550+ ch, V8 biturbo le plus emblématique",
        "color": 0x922B21,
    },
    # ---------------------------------------------------
    # VOLKSWAGEN — Golf / Polo / Arteon / Golf R
    # ---------------------------------------------------
    "golf_gti_r": {
        "label": "VW Golf GTI / Golf R / 2.0 TSI (MK7/8)", "emoji": "🚗",
        "make": "volkswagen", "model_id": "golf",
        "keywords": ["golf gti", "golf r", "golf 2.0 tsi", "golf 7 gti", "golf 8 gti", "golf gtd", "golf r mk7"],
        "engine_kw": ["gti", "golf r", "2.0 tsi", "ea888", "dsg", "4motion"],
        "min_year": 2015, "min_power": 180, "market_base": 20_000,
        "stage1_note": "Stage 1 GTI → 300 ch / Golf R → 380 ch, références absolues hot-hatch",
        "color": 0xE74C3C,
    },
    "polo_gti": {
        "label": "VW Polo GTI 2.0 TSI (AW)", "emoji": "🚗",
        "make": "volkswagen", "model_id": "polo",
        "keywords": ["polo gti", "polo 2.0 tsi", "polo aw", "polo gti 2018"],
        "engine_kw": ["gti", "2.0 tsi", "aw", "dsg"],
        "min_year": 2018, "min_power": 196, "market_base": 16_500,
        "stage1_note": "Stage 1 → 240–260 ch, châssis vif, parfait en ville",
        "color": 0x27AE60,
    },
    "arteon": {
        "label": "VW Arteon 2.0 TSI R-Line / Shooting Brake", "emoji": "🚗",
        "make": "volkswagen", "model_id": "arteon",
        "keywords": ["arteon 2.0 tsi", "arteon r-line", "arteon elegance", "arteon shooting brake"],
        "engine_kw": ["2.0 tsi", "r-line", "dsg", "4motion"],
        "min_year": 2017, "min_power": 150, "market_base": 21_000,
        "stage1_note": "Stage 1 → 270 ch sur 190ch, grand tourisme élégant sous-coté",
        "color": 0x2C3E50,
    },
    # ---------------------------------------------------
    # SEAT / CUPRA — Leon / Formentor
    # ---------------------------------------------------
    "seat_cupra": {
        "label": "Seat Leon Cupra / Cupra Formentor 2.0 TSI", "emoji": "🚗",
        "make": "seat", "model_id": "leon",
        "keywords": ["leon cupra", "cupra leon", "cupra formentor", "cupra 290", "cupra 300", "leon fr 2.0", "formentor 2.0"],
        "engine_kw": ["cupra", "2.0 tsi", "dsg", "ea888", "4drive"],
        "min_year": 2016, "min_power": 180, "market_base": 18_000,
        "stage1_note": "Stage 1 → 310–340 ch, meilleur rapport prix/perf du segment",
        "color": 0xC0392B,
    },
    # ---------------------------------------------------
    # SKODA — Octavia RS / Superb
    # ---------------------------------------------------
    "octavia_rs": {
        "label": "Skoda Octavia RS 2.0 TSI / RS 245", "emoji": "🚗",
        "make": "skoda", "model_id": "octavia",
        "keywords": ["octavia rs", "octavia 2.0 tsi", "octavia rs 245", "octavia combi rs", "skoda rs"],
        "engine_kw": ["rs", "2.0 tsi", "dsg", "ea888"],
        "min_year": 2016, "min_power": 180, "market_base": 17_500,
        "stage1_note": "Stage 1 → 270–290 ch, sleeper parfait, coffre géant",
        "color": 0x34495E,
    },
    "superb_280": {
        "label": "Skoda Superb 2.0 TSI / Sportline (3V)", "emoji": "🚗",
        "make": "skoda", "model_id": "superb",
        "keywords": ["superb 2.0 tsi", "superb sportline", "superb 280", "superb 4x4", "superb combi tsi"],
        "engine_kw": ["2.0 tsi", "sportline", "4x4", "dsg", "ea888"],
        "min_year": 2016, "min_power": 190, "market_base": 19_000,
        "stage1_note": "Stage 1 → 270 ch, confort S-classe Audi A6 pour le prix d'une Golf",
        "color": 0x2E4057,
    },
    # ---------------------------------------------------
    # WILDCARDS — Peugeot 308 GTi / Honda Civic Type R
    # ---------------------------------------------------
    "peugeot_308_gti": {
        "label": "Peugeot 308 GTi 270 / 250 (EP6)", "emoji": "🚗",
        "make": "peugeot", "model_id": "308",
        "keywords": ["308 gti", "308 gti 270", "308 gti 250", "peugeot gti"],
        "engine_kw": ["gti", "270", "ep6", "tds"],
        "min_year": 2015, "min_power": 250, "market_base": 16_000,
        "stage1_note": "Stage 1 → 310 ch, châssis parmi les plus précis du segment",
        "color": 0xD4AC0D,
    },
    "honda_civic_type_r": {
        "label": "Honda Civic Type R FK8 / FL5 (K20C1)", "emoji": "🏁",
        "make": "honda", "model_id": "civic",
        "keywords": ["civic type r", "type r fk8", "civic fk8", "k20c1", "type r 2017", "civic fl5"],
        "engine_kw": ["type r", "k20c1", "fk8", "fl5", "320 ch", "2.0 vtec turbo"],
        "min_year": 2017, "min_power": 310, "market_base": 30_000,
        "stage1_note": "Stage 1 → 380+ ch, recordman au Nürburgring FWD, fiabilité Honda",
        "color": 0xE74C3C,
    },
    "renault_megane_rs": {
        "label": "Renault Mégane RS 280 / 300 Trophy (M5Pt)", "emoji": "🚗",
        "make": "renault", "model_id": "megane",
        "keywords": ["megane rs", "megane 280", "megane 300", "rs trophy", "megane rs 2018", "4control"],
        "engine_kw": ["rs", "trophy", "280", "300", "1.8 turbo", "4control", "edc"],
        "min_year": 2018, "min_power": 280, "market_base": 21_000,
        "stage1_note": "Stage 1 → 330 ch + 4Control (4 roues directrices), châssis de rêve",
        "color": 0xF39C12,
    },
}

# ------------------------------------------------------------------
# FILTRES GLOBAUX
# ------------------------------------------------------------------
FILTERS = {
    "km_max": 130_000,
    "year_min": 2014,
    "year_max": 2026,
    "price_min": CONFIG["PRICE_MIN"],
    "price_max": CONFIG["PRICE_MAX"],
    "bonus_keywords": [
        # Entretien / historique
        "scheckheftgepflegt", "full service history", "serviceheft", "scheckheft",
        "carnet entretien", "carnet complet", "historique complet",
        "premiere main", "premier main", "1 main", "1ere main",
        "wenig km", "faible kilometrage",
        # Finitions sportives
        "s line", "amg line", "m sport", "m paket", "m-sport",
        "r-line", "r line", "rs", "gti", "cupra", "fr", "type r", "trophy",
        "competition", "performance", "sportline", "st-line",
        # Options premium
        "virtual cockpit", "digital cockpit", "head-up display", "hud",
        "bang olufsen", "harman kardon", "bowers wilkins", "burmester",
        "apple carplay", "android auto", "carplay",
        "toit panoramique", "toit ouvrant", "pano", "panorama",
        "cuir", "leder", "alcantara",
        "camera recul", "kamera", "360",
        "led", "matrix led", "laser", "full led",
        "park assist", "parkassist",
        # Transmissions sportives
        "dsg", "pdk", "zf8", "steptronic", "s tronic", "s-tronic", "dct", "edc",
        # Traction
        "quattro", "4matic", "xdrive", "4drive", "4motion", "4control",
        # Garantie
        "garantie constructeur", "garantie", "garantie 1 an",
    ],
    "blacklist": [
        # Dommages structurels / mécaniques
        "unfall", "unfallschaden", "unfallwagen",
        "hagelschaden", "hagelschaeden",
        "motorschaden", "getriebeschaden", "getriebebschaden",
        "rost", "rostschaden", "durchgerostet",
        "wasserschaden", "brandschaden", "inondé", "flood",
        # Statut véhicule
        "bastlerfahrzeug", "bastler", "defekt", "defekte",
        "nicht fahrbereit", "non-runner",
        "rebuilt", "salvage", "write-off",
        "export", "exportfahrzeug",
        # Français
        "accidente", "accidenté", "sinistre",
        "epave", "épave", "non roulant",
        "pour pieces", "pour pièces",
        "a reparer", "à réparer",
        "moteur hs", "boite hs", "boîte hs",
        "sans ct", "sans controle technique",
        "rouille", "rouillé",
        # Fraude potentielle
        "km non garanti", "km non certifié",
    ],
}

# ------------------------------------------------------------------
# GÉNÉRATEUR D'URLs AUTOMATIQUE
# ------------------------------------------------------------------
def _build_mobile_de_urls():
    MOBILE_IDS = {
        ("volkswagen", "golf"): "14900:18",
        ("volkswagen", "polo"): "14900:51",
        ("volkswagen", "arteon"): "14900:130",
        ("audi", "a3"): "1900:9",
        ("audi", "a4"): "1900:11",
        ("audi", "a5"): "1900:12",
        ("audi", "rs3"): "1900:91",
        ("bmw", "1er"): "3500:17",
        ("bmw", "3er"): "3500:19",
        ("bmw", "4er"): "3500:21",
        ("bmw", "5er"): "3500:22",
        ("bmw", "m2"): "3500:52",
        ("mercedes", "a-klasse"): "17200:12",
        ("mercedes", "cla"): "17200:28",
        ("mercedes", "c-klasse"): "17200:14",
        ("seat", "leon"): "18700:9",
        ("skoda", "octavia"): "19300:17",
        ("skoda", "superb"): "19300:19",
        ("peugeot", "308"): "20100:16",
        ("honda", "civic"): "10000:7",
        ("renault", "megane"): "21100:24",
    }
    base = "https://suchen.mobile.de/fahrzeuge/search.html"
    urls, seen = [], set()
    for pk, p in MODEL_PROFILES.items():
        key = (p["make"], p["model_id"])
        if key in seen:
            continue
        seen.add(key)
        ms = MOBILE_IDS.get(key, "")
        params = {
            "dam": "0", "isSearchRequest": "true", "s": "Car",
            "sb": "rel", "vc": "Car", "cy": "DE",
            "priceMin": str(FILTERS["price_min"]),
            "priceMax": str(FILTERS["price_max"]),
            "mileageMax": str(FILTERS["km_max"]),
            "firstRegistrationYearMin": str(FILTERS["year_min"]),
            "damaged_listing": "false",
        }
        if ms:
            params["ms"] = ms
        urls.append((f"{base}?{urlencode(params)}", pk))
    return urls


def _build_autoscout24_urls():
    MAKE_IDS = {
        "volkswagen": "74", "audi": "9", "bmw": "16",
        "mercedes": "58", "seat": "66", "skoda": "67",
        "peugeot": "28", "honda": "32", "renault": "37",
    }
    MODEL_IDS = {
        ("volkswagen", "golf"): "91",
        ("volkswagen", "polo"): "254",
        ("volkswagen", "arteon"): "22706",
        ("audi", "a3"): "4",
        ("audi", "a4"): "7",
        ("audi", "a5"): "8",
        ("audi", "rs3"): "59",
        ("bmw", "1er"): "790",
        ("bmw", "3er"): "3",
        ("bmw", "4er"): "839",
        ("bmw", "5er"): "6",
        ("bmw", "m2"): "18483",
        ("mercedes", "a-klasse"): "3",
        ("mercedes", "cla"): "297",
        ("mercedes", "c-klasse"): "5",
        ("seat", "leon"): "24",
        ("skoda", "octavia"): "20",
        ("skoda", "superb"): "24",
        ("peugeot", "308"): "31",
        ("honda", "civic"): "7",
        ("renault", "megane"): "16",
    }
    base = "https://www.autoscout24.de/lst"
    urls, seen = [], set()
    for pk, p in MODEL_PROFILES.items():
        mk, md = p["make"], p["model_id"]
        combo = (mk, md)
        if combo in seen:
            continue
        seen.add(combo)
        params = {
            "atype": "C", "cy": "D", "damaged_listing": "exclude",
            "fregfrom": str(FILTERS["year_min"]),
            "kmto": str(FILTERS["km_max"]),
            "pricefrom": str(FILTERS["price_min"]),
            "priceto": str(FILTERS["price_max"]),
            "sort": "age", "desc": "0", "ustate": "N,U",
        }
        if MAKE_IDS.get(mk):
            params["mmvmk0"] = MAKE_IDS[mk]
        if MODEL_IDS.get(combo):
            params["mmvmo0"] = MODEL_IDS[combo]
        urls.append((f"{base}?{urlencode(params)}", pk))
    return urls


def _build_leboncoin_urls():
    params = {
        "category": "2",
        "price": f"{FILTERS['price_min']}-{FILTERS['price_max']}",
        "mileage": f"0-{FILTERS['km_max']}",
        "regdate": f"{FILTERS['year_min']}-max",
        "fuel": "1", "sort": "time", "order": "desc",
    }
    return [(f"https://www.leboncoin.fr/recherche?{urlencode(params)}", "leboncoin_all")]


def _build_heycar_urls():
    params = {
        "maxPrice": str(FILTERS["price_max"]),
        "minPrice": str(FILTERS["price_min"]),
        "maxMileage": str(FILTERS["km_max"]),
        "minFirstRegistration": str(FILTERS["year_min"]),
        "fuel": "PETROL",
    }
    return [(f"https://www.hey.car/gebrauchtwagen?{urlencode(params)}", "heycar_all")]


def build_all_search_urls():
    return {
        "mobile_de": _build_mobile_de_urls(),
        "autoscout24": _build_autoscout24_urls(),
        "leboncoin": _build_leboncoin_urls(),
        "heycar": _build_heycar_urls(),
    }

# ------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(CONFIG["LOG_PATH"], encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("CarHunter")

# ------------------------------------------------------------------
# DATA MODEL
# ------------------------------------------------------------------
@dataclass
class Car:
    title: str
    price: int
    km: int
    year: int
    fuel: str = "?"
    transmission: str = "?"
    power_hp: int = 0
    location: str = "?"
    seller_type: str = "?"
    image_url: str = ""
    link: str = ""
    source: str = ""
    profile_key: str = ""
    description: str = ""
    deal_score: int = 0
    market_price: int = 0
    savings: int = 0
    first_seen: str = ""
    uid: str = field(default="", repr=False)

    def __post_init__(self):
        self.uid = hashlib.md5(self.link.encode()).hexdigest()[:12]
        if not self.first_seen:
            self.first_seen = datetime.now().isoformat(timespec="seconds")

# ------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------
class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS seen_cars (
                uid TEXT PRIMARY KEY, link TEXT, title TEXT,
                price INTEGER, deal_score INTEGER, source TEXT,
                profile_key TEXT, first_seen TEXT, notified INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS stats (
                date TEXT PRIMARY KEY, scanned INTEGER DEFAULT 0, deals_sent INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def is_seen(self, uid):
        return self.conn.execute("SELECT 1 FROM seen_cars WHERE uid=?", (uid,)).fetchone() is not None

    def mark_seen(self, car, notified):
        self.conn.execute("""
            INSERT OR REPLACE INTO seen_cars
            (uid,link,title,price,deal_score,source,profile_key,first_seen,notified)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (car.uid, car.link, car.title, car.price, car.deal_score,
              car.source, car.profile_key, car.first_seen, int(notified)))
        self.conn.commit()

    def increment_stats(self, scanned=0, deals_sent=0):
        today = datetime.now().strftime("%Y-%m-%d")
        self.conn.execute("""
            INSERT INTO stats (date,scanned,deals_sent) VALUES (?,?,?)
            ON CONFLICT(date) DO UPDATE SET
            scanned=scanned+excluded.scanned,
            deals_sent=deals_sent+excluded.deals_sent
        """, (today, scanned, deals_sent))
        self.conn.commit()

    def get_stats(self):
        r = self.conn.execute("SELECT SUM(scanned),SUM(deals_sent),COUNT(DISTINCT date) FROM stats").fetchone()
        return {"total_scanned": r[0] or 0, "total_sent": r[1] or 0, "days": r[2] or 0}

# ------------------------------------------------------------------
# HTTP
# ------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def make_session():
    s = requests.Session()
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,fr-FR;q=0.8,en;q=0.6",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    })
    return s


def get_page(url, session, retries=3):
    for attempt in range(retries):
        try:
            session.headers["User-Agent"] = random.choice(USER_AGENTS)
            proxies = None
            if CONFIG["PROXIES"]:
                p = random.choice(CONFIG["PROXIES"])
                proxies = {"http": p, "https": p}
            time.sleep(random.uniform(*CONFIG["REQUEST_DELAY"]))
            r = session.get(url, timeout=22, proxies=proxies)
            r.raise_for_status()
            return r.text
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 429:
                w = 90 * (attempt + 1)
                log.warning(f"⏳ Rate-limited {w}s")
                time.sleep(w)
            elif code in (403, 503):
                log.warning(f"🚫 Bloqué {code}")
                time.sleep(40)
            else:
                log.error(f"HTTP {code} — {url[:55]}")
                break
        except Exception as e:
            log.warning(f"Erreur req (#{attempt+1}): {e}")
            time.sleep(8 * (attempt + 1))
    return None

# ------------------------------------------------------------------
# PARSERS
# ------------------------------------------------------------------
def _int(t, d=0):
    for n in re.findall(r"\d+", re.sub(r"[\s.,\u202f\xa0]", "", str(t))):
        if len(n) <= 7:
            return int(n)
    return d


def _year(t):
    m = re.search(r"\b(20[12]\d|201\d)\b", t)
    return int(m.group()) if m else 0


def _km(t):
    m = re.search(r"([\d\s\.,]+)\s*km", t, re.I)
    return _int(m.group(1)) if m else 0


def _fuel(t):
    t = t.lower()
    for f, kws in [
        ("Diesel", ["diesel", "tdi", "cdi"]),
        ("Essence", ["benzin", "essence", "tfsi", "tsi", "turbo"]),
        ("Hybride", ["hybrid", "phev"]),
        ("Électrique", ["elektro", "electric", "bev"]),
        ("GPL", ["lpg", "gpl"]),
    ]:
        if any(k in t for k in kws):
            return f
    return "?"


def _trans(t):
    t = t.lower()
    if any(k in t for k in ["dsg", "s tronic", "pdk", "automatik", "zf", "steptronic", "automat"]):
        return "Auto/DSG"
    if any(k in t for k in ["schalt", "manuel", "manual", "6-gang", "getriebe"]):
        return "Manuelle"
    return "?"


def _hp(t):
    m = re.search(r"(\d{2,4})\s*(?:ch|ps|kw)", t, re.I)
    if not m:
        return 0
    hp = int(m.group(1))
    return int(hp * 1.36) if "kw" in m.group(0).lower() else hp


def _img(item):
    el = item.select_one("img[src], img[data-src]")
    return (el.get("src") or el.get("data-src", "")) if el else ""


def parse_mobile_de(html, profile_key=""):
    soup = BeautifulSoup(html, "lxml")
    cars = []
    items = (
        soup.select("article.cBox-body--resultitem") or
        soup.select("[data-listing-id]") or
        soup.select(".result-item")
    )
    for item in items:
        try:
            t_el = item.select_one("h2.title, .listing-title, span.title-block--title")
            title = t_el.get_text(strip=True) if t_el else ""
            p_el = item.select_one(".price-block--price, span.price, .listing-price")
            price = _int(p_el.get_text(strip=True)) if p_el else 0
            l_el = item.select_one("a[href*='/fahrzeuge/'], a[href*='mobile.de'], a[href]")
            link = l_el["href"] if l_el else ""
            if link and not link.startswith("http"):
                link = "https://www.mobile.de" + link
            body = item.get_text(" ", strip=True)
            loc_el = item.select_one(".seller-info__location, .listing-location")
            loc = loc_el.get_text(strip=True)[:50] if loc_el else "Deutschland"
            s_el = item.select_one(".seller-info__type, .badge--dealer")
            seller = "pro" if s_el and "händler" in s_el.get_text(strip=True).lower() else "private"
            if not title or price == 0 or not link:
                continue
            cars.append(Car(
                title=title, price=price, km=_km(body), year=_year(body),
                fuel=_fuel(body), transmission=_trans(body), power_hp=_hp(body),
                link=link, source="mobile.de", profile_key=profile_key,
                location=loc, seller_type=seller, image_url=_img(item), description=body[:300],
            ))
        except Exception as e:
            log.debug(f"[mobile.de] {e}")
    log.info(f"[mobile.de/{profile_key}] {len(cars)} annonces")
    return cars


def parse_autoscout24(html, profile_key=""):
    soup = BeautifulSoup(html, "lxml")
    cars = []
    items = (
        soup.select("article.cldt-summary-full-item") or
        soup.select("article[data-item-name='listing']") or
        soup.select("article")
    )
    for item in items:
        try:
            t_el = item.select_one("h2, .ListItem_title__znV2I, a[data-testid='listing-link']")
            title = t_el.get_text(strip=True) if t_el else ""
            p_el = item.select_one("[data-testid='price-label'], .Price_price__APlgs, [class*='price']")
            price = _int(p_el.get_text(strip=True)) if p_el else 0
            l_el = item.select_one("a[href*='/annonce/'], a[href*='/fahrzeug/'], a[href]")
            link = l_el["href"] if l_el else ""
            if link and not link.startswith("http"):
                link = "https://www.autoscout24.de" + link
            body = item.get_text(" ", strip=True)
            loc_el = item.select_one("[data-testid='listing-location']")
            loc = loc_el.get_text(strip=True)[:50] if loc_el else "Deutschland"
            if not title or price == 0 or not link:
                continue
            cars.append(Car(
                title=title, price=price, km=_km(body), year=_year(body),
                fuel=_fuel(body), transmission=_trans(body), power_hp=_hp(body),
                link=link, source="autoscout24", profile_key=profile_key,
                location=loc, image_url=_img(item), description=body[:300],
            ))
        except Exception as e:
            log.debug(f"[autoscout24] {e}")
    log.info(f"[autoscout24/{profile_key}] {len(cars)} annonces")
    return cars


def parse_leboncoin(html, profile_key=""):
    soup = BeautifulSoup(html, "lxml")
    cars = []
    items = (
        soup.select("li[data-qa-id='aditem_container']") or
        soup.select("article[data-qa-id='aditem']") or
        soup.select("li.styles_adItem__GJt3r")
    )
    for item in items:
        try:
            t_el = item.select_one("p[data-qa-id='aditem_title'], h2")
            title = t_el.get_text(strip=True) if t_el else ""
            p_el = item.select_one("span[data-qa-id='aditem_price'], [class*='price']")
            price = _int(p_el.get_text(strip=True)) if p_el else 0
            l_el = item.select_one("a[href]")
            link = l_el["href"] if l_el else ""
            if link and not link.startswith("http"):
                link = "https://www.leboncoin.fr" + link
            body = item.get_text(" ", strip=True)
            loc_el = item.select_one("[data-qa-id='aditem_location']")
            loc = loc_el.get_text(strip=True)[:50] if loc_el else "France"
            if not title or price == 0 or not link:
                continue
            cars.append(Car(
                title=title, price=price, km=_km(body), year=_year(body),
                link=link, source="leboncoin", profile_key=profile_key,
                location=loc, image_url=_img(item), description=body[:300],
            ))
        except Exception as e:
            log.debug(f"[leboncoin] {e}")
    log.info(f"[leboncoin] {len(cars)} annonces")
    return cars


def parse_heycar(html, profile_key=""):
    soup = BeautifulSoup(html, "lxml")
    cars = []
    items = (
        soup.select("article.vehicle-card") or
        soup.select("[data-testid='vehicle-card']") or
        soup.select("[class*='VehicleCard']")
    )
    for item in items:
        try:
            t_el = item.select_one("h2, h3, [data-testid='vehicle-name'], [class*='title']")
            title = t_el.get_text(strip=True) if t_el else ""
            p_el = item.select_one("[data-testid='price'], [class*='price']")
            price = _int(p_el.get_text(strip=True)) if p_el else 0
            l_el = item.select_one("a[href]")
            link = l_el["href"] if l_el else ""
            if link and not link.startswith("http"):
                link = "https://www.hey.car" + link
            body = item.get_text(" ", strip=True)
            if not title or price == 0 or not link:
                continue
            cars.append(Car(
                title=title, price=price, km=_km(body), year=_year(body),
                fuel=_fuel(body), link=link, source="heycar", profile_key=profile_key,
                location="Deutschland", image_url=_img(item), description=body[:300],
            ))
        except Exception as e:
            log.debug(f"[heycar] {e}")
    log.info(f"[heycar] {len(cars)} annonces")
    return cars


PARSERS = {
    "mobile_de": parse_mobile_de,
    "autoscout24": parse_autoscout24,
    "leboncoin": parse_leboncoin,
    "heycar": parse_heycar,
}

# ------------------------------------------------------------------
# MATCHING PROFIL
# ------------------------------------------------------------------
def match_profile(car):
    text = (car.title + " " + car.description).lower()
    if car.profile_key and car.profile_key in MODEL_PROFILES:
        p = MODEL_PROFILES[car.profile_key]
        if any(kw in text for kw in p["keywords"]):
            return car.profile_key
    scores = {
        pk: sum(1 for kw in p["keywords"] if kw in text)
        for pk, p in MODEL_PROFILES.items()
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else None

# ------------------------------------------------------------------
# FILTRES
# ------------------------------------------------------------------
def passes_filters(car, profile):
    if not (FILTERS["price_min"] <= car.price <= FILTERS["price_max"]):
        return False
    if car.km and car.km > FILTERS["km_max"]:
        return False
    if car.year:
        if car.year < FILTERS["year_min"] or car.year > FILTERS["year_max"]:
            return False
        if profile and car.year < profile.get("min_year", FILTERS["year_min"]):
            return False
    if profile and car.power_hp and profile.get("min_power", 0) > 0:
        if car.power_hp < profile["min_power"] * 0.85:
            return False
    text = (car.title + " " + car.description).lower()
    if any(kw in text for kw in FILTERS["blacklist"]):
        return False
    return True

# ------------------------------------------------------------------
# ESTIMATION MARCHÉ
# ------------------------------------------------------------------
def estimate_market_price(car, profile):
    base = profile["market_base"] if profile else 16_000
    age = max(0, datetime.now().year - car.year) if car.year else 4
    base = base * (0.92 ** age)
    km_over = max(0, (car.km or 80_000) - 80_000)
    base -= (km_over // 10_000) * 200
    if car.transmission == "Auto/DSG":
        base += 800
    if car.seller_type == "private":
        base += 600
    return max(1_500, int(base))

# ------------------------------------------------------------------
# SCORING /100
# ------------------------------------------------------------------
def score_car(car, profile):
    s = 50
    if car.market_price > 0:
        r = car.price / car.market_price
        if r < 0.60:
            s += 32
        elif r < 0.70:
            s += 24
        elif r < 0.80:
            s += 16
        elif r < 0.88:
            s += 8
        elif r < 0.96:
            s += 2
        else:
            s -= 8
    km = car.km or 80_000
    if km < 40_000:
        s += 12
    elif km < 70_000:
        s += 8
    elif km < 100_000:
        s += 3
    elif km < 120_000:
        s -= 2
    else:
        s -= 8
    if car.year:
        age = datetime.now().year - car.year
        if age <= 2:
            s += 10
        elif age <= 4:
            s += 6
        elif age <= 7:
            s += 2
        elif age <= 10:
            s -= 2
        else:
            s -= 6
    text = (car.title + " " + car.description).lower()
    bonuses = sum(1 for kw in FILTERS["bonus_keywords"] if kw in text)
    s += min(bonuses * 3, 12)
    if car.transmission == "Auto/DSG":
        s += 4
    if car.seller_type == "private":
        s += 5
    s += {"heycar": 6, "mobile.de": 3, "autoscout24": 3, "leboncoin": 0}.get(car.source, 0)
    if profile:
        s += min(sum(1 for kw in profile["engine_kw"] if kw in text) * 4, 10)
    if car.price <= CONFIG["PRICE_TARGET"]:
        s += 4
    return max(0, min(100, s))

# ------------------------------------------------------------------
# DISCORD
# ------------------------------------------------------------------
def score_color(s):
    if s >= 85:
        return 0x00FF7F
    if s >= 75:
        return 0x2ECC71
    if s >= 65:
        return 0xF1C40F
    return 0xE67E22


def score_label(s):
    if s >= 85:
        return "🏆 EXCEPTIONNEL"
    if s >= 75:
        return "🔥 TRÈS BON DEAL"
    if s >= 65:
        return "✅ BON DEAL"
    return "👀 INTÉRESSANT"


def bar(ratio):
    pct = max(0, min(60, int((1 - ratio) * 100)))
    filled = min(10, pct // 5)
    return f"`{'█' * filled}{'░' * (10 - filled)}` **-{pct}%** vs marché"


def send_discord(car, profile):
    url = CONFIG["DISCORD_WEBHOOK_URL"]
    if not url or "VOTRE_WEBHOOK" in url:
        log.warning("⚠️ Webhook Discord non configuré")
        return False
    ratio = car.price / car.market_price if car.market_price else 1.0
    flag = {"mobile.de": "🇩🇪", "autoscout24": "🇩🇪", "leboncoin": "🇫🇷", "heycar": "🇩🇪"}.get(car.source, "🌍")
    p_emoji = profile["emoji"] if profile else "🚗"
    p_label = profile["label"] if profile else car.source
    stage1 = profile.get("stage1_note", "") if profile else ""
    fields = [
        {"name": "💶 Prix", "value": f"**{car.price:,} €**", "inline": True},
        {"name": "📊 Marché estimé", "value": f"~{car.market_price:,} €", "inline": True},
        {"name": "💰 Économie", "value": f"**{car.savings:+,} €**", "inline": True},
        {"name": "📅 Année", "value": str(car.year) if car.year else "?", "inline": True},
        {"name": "🛣️ Km", "value": f"{car.km:,} km" if car.km else "?", "inline": True},
        {"name": "⚙️ Boîte", "value": car.transmission, "inline": True},
        {"name": "⛽ Carburant", "value": car.fuel, "inline": True},
        {"name": "📍 Lieu", "value": car.location[:35], "inline": True},
        {"name": "👤 Vendeur", "value": car.seller_type.capitalize(), "inline": True},
        {"name": "📉 Décote", "value": bar(ratio), "inline": False},
    ]
    if stage1:
        fields.append({"name": "🔧 Stage 1", "value": f"*{stage1}*", "inline": False})
    fields += [
        {"name": "🌐 Source", "value": f"{flag} **{car.source}**", "inline": True},
        {"name": "🏷️ Profil", "value": f"{p_emoji} {p_label}", "inline": True},
        {"name": "⭐ Score", "value": f"**{car.deal_score}/100**", "inline": True},
    ]
    payload = {
        "username": "🚗 CarHunter DE Pro",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3097/3097144.png",
        "embeds": [{
            "title": f"{score_label(car.deal_score)} {p_emoji} {car.title[:75]}",
            "url": car.link,
            "color": score_color(car.deal_score),
            "fields": fields,
            "footer": {"text": f"CarHunter DE • {datetime.now().strftime('%H:%M %d/%m/%Y')} • uid {car.uid}"},
        }],
    }
    if car.image_url and car.image_url.startswith("http"):
        payload["embeds"][0]["thumbnail"] = {"url": car.image_url}
    try:
        r = requests.post(url, json=payload, timeout=12)
        r.raise_for_status()
        log.info(f"✅ Discord → {car.title[:50]} | {car.price}€ | score {car.deal_score}")
        return True
    except Exception as e:
        log.error(f"Discord error: {e}")
        return False


def send_discord_summary(stats, deals):
    url = CONFIG["DISCORD_WEBHOOK_URL"]
    if not url or "VOTRE_WEBHOOK" in url:
        return
    profiles_txt = "\n".join(f"{p['emoji']} {p['label']}" for p in MODEL_PROFILES.values())
    payload = {
        "username": "🚗 CarHunter DE Pro",
        "embeds": [{
            "title": "📊 Rapport horaire",
            "color": 0x3498DB,
            "description": (
                f"**Deals ce cycle :** {deals}\n"
                f"**Total scannées :** {stats['total_scanned']:,}\n"
                f"**Notifications envoyées :** {stats['total_sent']:,}\n"
                f"**Jours actifs :** {stats['days']}\n\n"
                f"**Modèles surveillés :**\n{profiles_txt}"
            ),
            "footer": {"text": f"CarHunter DE • {datetime.now().strftime('%H:%M %d/%m/%Y')}"},
        }],
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass

# ------------------------------------------------------------------
# ORCHESTRATEUR
# ------------------------------------------------------------------
def scrape_all(session):
    all_urls = build_all_search_urls()
    all_cars = []
    for source_key, url_list in all_urls.items():
        parser = PARSERS.get(source_key)
        if not parser:
            continue
        for url, profile_key in url_list:
            log.info(f"🔍 {source_key} [{profile_key}] — {url[:80]}...")
            html = get_page(url, session)
            if html:
                all_cars.extend(parser(html, profile_key))
            else:
                log.warning(f"❌ Échec {url[:60]}")
    return all_cars


def process_cycle(db, session):
    cars = scrape_all(session)
    db.increment_stats(scanned=len(cars))
    deals_sent = 0
    for car in cars:
        if db.is_seen(car.uid):
            continue
        pk = match_profile(car)
        profile = MODEL_PROFILES.get(pk) if pk else None
        if pk:
            car.profile_key = pk
        if not passes_filters(car, profile):
            db.mark_seen(car, notified=False)
            continue
        car.market_price = estimate_market_price(car, profile)
        car.savings = car.market_price - car.price
        car.deal_score = score_car(car, profile)
        is_deal = (
            car.deal_score >= CONFIG["DEAL_SCORE_MIN"] and
            car.price <= car.market_price * CONFIG["PRICE_BELOW_MARKET"]
        )
        notified = False
        if is_deal:
            notified = send_discord(car, profile)
            if notified:
                deals_sent += 1
                db.increment_stats(deals_sent=1)
        db.mark_seen(car, notified=notified)
        log.debug(
            f"[{car.source}] {car.title[:38]:38s} | {car.price:>6}€ | {car.km:>7}km | "
            f"score {car.deal_score:>3} | deal={is_deal} | {pk or '—'}"
        )
    log.info(f"✅ Cycle terminé — {len(cars)} annonces | {deals_sent} deals envoyés")
    return deals_sent

# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    all_urls = build_all_search_urls()
    total_url = sum(len(v) for v in all_urls.values())
    log.info("-" * 65)
    log.info("🚗 CarHunter DE Pro — Sportives Allemandes Stage 1")
    log.info("-" * 65)
    log.info(f"🔗 Webhook : {'✅ configuré' if 'VOTRE_WEBHOOK' not in CONFIG['DISCORD_WEBHOOK_URL'] else '❌ NON configuré'}")
    log.info(f"💶 Budget : {CONFIG['PRICE_MIN']:,}€ → {CONFIG['PRICE_MAX']:,}€ (cible {CONFIG['PRICE_TARGET']:,}€)")
    log.info(f"🔎 Filtres : ≤{FILTERS['km_max']:,}km | ≥{FILTERS['year_min']} | Essence | Blacklist: {len(FILTERS['blacklist'])} termes")
    log.info(f"📋 Modèles : {len(MODEL_PROFILES)} profils :")
    for p in MODEL_PROFILES.values():
        log.info(f"   {p['emoji']} {p['label']:35s} | base marché {p['market_base']:,}€ | {p.get('stage1_note', '')[:55]}")
    log.info(f"🌐 URLs : {total_url} générées automatiquement")
    log.info(f"⏱️ Cycle : toutes les {CONFIG['CHECK_INTERVAL']}s")
    log.info("-" * 65)
    db = Database(CONFIG["DB_PATH"])
    session = make_session()
    last_summary = datetime.now()
    cycle = 0
    while True:
        cycle += 1
        log.info(f"\n{'-' * 55}")
        log.info(f"🔄 CYCLE #{cycle} — {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")
        log.info(f"{'-' * 55}")
        try:
            deals = process_cycle(db, session)
            if datetime.now() - last_summary > timedelta(hours=1):
                send_discord_summary(db.get_stats(), deals)
                last_summary = datetime.now()
        except KeyboardInterrupt:
            log.info("\n🛑 Arrêt utilisateur")
            break
        except Exception:
            log.error(f"Erreur:\n{traceback.format_exc()}")
        log.info(f"⏳ Prochain cycle dans {CONFIG['CHECK_INTERVAL']}s...")
        time.sleep(CONFIG["CHECK_INTERVAL"])


if __name__ == "__main__":
    main()
