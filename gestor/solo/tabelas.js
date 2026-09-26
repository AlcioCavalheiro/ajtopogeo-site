/* Tabelas da Recomendação de Solo (Gestor AJ TopoGeo).
 *
 * Extraídas das publicações — cada cultura tem o campo "fonte":
 *   DEF.b100 .... Boletim 100, IAC, ed. 2022 (SP) — P em resina
 *   DEF.mg ...... 5ª Aproximação, CFSEMG 1999 (MG) — P e K em Mehlich-1
 *   DEF.cerrado . Embrapa Cerrados (Sousa & Lobato 2004; Embrapa Soja 2020)
 *   MGP ......... classes de P por argila e de K da 5ª Aproximação
 *   MICRO ....... limites (e doses do Cerrado) de micronutrientes
 *
 * NÃO altere números sem conferir no PDF de origem.
 * O corpo abaixo é JSON puro (mesmo conteúdo de dados/tabelas.json do projeto
 * original); o invólucro só serve para carregar por <script> no Gestor (funciona
 * offline e em file://) e por require() nos testes.
 */
(function (root, dados) {
  if (typeof module === "object" && module.exports) module.exports = dados;
  else root.SoloTabelas = dados;
})(typeof self !== "undefined" ? self : this, {
 "DEF": {
  "b100": {
   "nome": "Boletim 100 (IAC, 2022)",
   "crops": {
    "soja": {
     "nome": "Soja",
     "fonte": "Boletim 100, ed. 2022, item 3.6",
     "V2": 70,
     "Mgmin": 8,
     "prod": [
      "< 3,0 t/ha",
      "3,0–4,0 t/ha",
      "4,0–5,0 t/ha",
      "> 5,0 t/ha"
     ],
     "tmed": [
      2.5,
      3.5,
      4.5,
      5.5
     ],
     "Npl": [
      0,
      0,
      0,
      0
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        120,
        140,
        160,
        null
       ],
       [
        80,
        100,
        120,
        140
       ],
       [
        30,
        40,
        60,
        80
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        100,
        120,
        140,
        160
       ],
       [
        60,
        80,
        100,
        120
       ],
       [
        40,
        60,
        80,
        100
       ]
      ]
     },
     "Ksulco": 50,
     "Pzero": {
      "acima": 80,
      "dose": 20
     },
     "Kzero": 6,
     "fosfatagem": {
      "ate": 6,
      "dose": 100
     },
     "S": {
      "porT": 15,
      "se20a40": 15
     },
     "micro": {
      "Mn": [
       [
        1.31,
        5
       ]
      ]
     },
     "v2040": 40,
     "nota": "Inocular com Bradyrhizobium; 50 g/ha de Mo e 3–5 g/ha de Co nas sementes. Após milho ou gramíneas de cobertura pode-se usar 20–30 kg/ha de N no plantio. Cultivares RR com Mn médio: 2,5 kg/ha de Mn."
    },
    "milho": {
     "nome": "Milho grão (verão ou safrinha)",
     "fonte": "Boletim 100, ed. 2022, item 3.5",
     "V2": 70,
     "Mgmin": 8,
     "prod": [
      "< 6 t/ha",
      "6–8 t/ha",
      "8–10 t/ha",
      "10–12 t/ha",
      "> 12 t/ha"
     ],
     "Npl": [
      30,
      30,
      30,
      30,
      30
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        90,
        100,
        120,
        null,
        null
       ],
       [
        60,
        70,
        90,
        110,
        120
       ],
       [
        30,
        40,
        60,
        70,
        80
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        70,
        90,
        100,
        110,
        120
       ],
       [
        40,
        50,
        70,
        90,
        100
       ],
       [
        30,
        30,
        40,
        50,
        60
       ]
      ]
     },
     "Ntot": {
      "alta": [
       90,
       120,
       160,
       200,
       220
      ],
      "media": [
       60,
       90,
       120,
       140,
       160
      ]
     },
     "NKsulco": 80,
     "Pzero": {
      "acima": 80,
      "dose": 30
     },
     "Kzero": 6,
     "S": {
      "fix": [
       20,
       20,
       40,
       40,
       40
      ]
     },
     "micro": {
      "Zn": [
       [
        0.6,
        4
       ],
       [
        1.21,
        2
       ]
      ]
     },
     "respNota": "Alta: anos de milho ou não leguminosas, primeiros anos de plantio direto, muita palha de gramínea, solo arenoso. Média e baixa: após leguminosa, adubo orgânico, safrinha após soja, plantio direto estabilizado com leguminosas.",
     "nota": "Do N total, 30–60 kg/ha vão no plantio. Coberturas acima de 80 kg/ha: parcelar em duas (2–3 e 6–7 folhas). Silagem: repor 30 kg de K₂O por 10 t de massa fresca na cultura seguinte."
    },
    "sorgo": {
     "nome": "Sorgo granífero",
     "fonte": "Boletim 100, ed. 2022, item 3.7.7",
     "V2": 70,
     "Mgmin": 8,
     "prod": [
      "< 4 t/ha",
      "4–6 t/ha",
      "6–8 t/ha",
      "> 8 t/ha"
     ],
     "Npl": [
      20,
      20,
      20,
      20
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        70,
        90,
        110,
        120
       ],
       [
        40,
        60,
        80,
        90
       ],
       [
        30,
        40,
        60,
        70
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        60,
        80,
        100,
        120
       ],
       [
        40,
        50,
        60,
        80
       ],
       [
        20,
        30,
        40,
        50
       ]
      ]
     },
     "Ntot": {
      "alta": [
       50,
       80,
       120,
       150
      ],
      "media": [
       30,
       50,
       80,
       100
      ]
     },
     "NKsulco": 80,
     "Pzero": {
      "acima": 80,
      "dose": 25
     },
     "Kzero": 6,
     "S": {
      "fix": [
       20,
       20,
       30,
       30
      ]
     },
     "micro": {
      "Zn": [
       [
        0.6,
        4
       ],
       [
        1.21,
        2
       ]
      ]
     },
     "nota": "Plantio em fevereiro–março: faça a calagem antes da cultura de verão."
    },
    "feijao": {
     "nome": "Feijão",
     "fonte": "Boletim 100, ed. 2022, item 3.8.5",
     "V2": 70,
     "Mgmin": 8,
     "prod": [
      "< 3,0 t/ha",
      "3,0–4,0 t/ha",
      "4,0–5,0 t/ha",
      "> 5,0 t/ha"
     ],
     "tmed": [
      2.5,
      3.5,
      4.5,
      5.5
     ],
     "Npl": [
      10,
      20,
      30,
      40
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        80,
        100,
        120,
        140
       ],
       [
        40,
        60,
        80,
        100
       ],
       [
        20,
        30,
        40,
        40
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        60,
        100,
        120,
        140
       ],
       [
        60,
        80,
        100,
        120
       ],
       [
        30,
        40,
        60,
        80
       ]
      ]
     },
     "Ncob": {
      "alta": [
       80,
       100,
       110,
       120
      ],
      "media": [
       40,
       40,
       60,
       80
      ]
     },
     "Ksulco": 50,
     "Pzero": {
      "acima": 80,
      "dose": 30
     },
     "Kzero": 6,
     "S": {
      "porT": 10
     },
     "micro": {
      "Zn": [
       [
        0.6,
        3
       ]
      ],
      "B": [
       [
        0.2,
        1
       ]
      ],
      "Mn": [
       [
        1.3,
        1.5
       ]
      ]
     },
     "respNota": "Alta: irrigado, solo arenoso, após gramíneas (plantio direto recente). Média e baixa: após leguminosas, pousio de 2+ anos, adubação orgânica frequente, plantio direto consolidado.",
     "nota": "Mo: 20–50 g/ha nas sementes ou 250 g/ha foliar até V4–V5."
    },
    "trigo": {
     "nome": "Trigo e triticale de sequeiro",
     "fonte": "Boletim 100, ed. 2022, item 3.7.9",
     "V2": 70,
     "Mgmin": 8,
     "prod": [
      "< 3,0 t/ha",
      "3,0–4,5 t/ha",
      "> 4,5 t/ha"
     ],
     "Npl": [
      20,
      20,
      20
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        90,
        100,
        120
       ],
       [
        40,
        60,
        80
       ],
       [
        30,
        40,
        50
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        70,
        90,
        120
       ],
       [
        40,
        60,
        80
       ],
       [
        20,
        30,
        40
       ]
      ]
     },
     "Ncob": {
      "alta": [
       50,
       70,
       90
      ],
      "media": [
       30,
       50,
       70
      ]
     },
     "Ksulco": 50,
     "Pzero": {
      "acima": 80,
      "dose": 30
     },
     "Kzero": 6,
     "S": {
      "fix": [
       20,
       20,
       20
      ]
     },
     "micro": {
      "Zn": [
       [
        0.6,
        3
       ],
       [
        1.21,
        2
       ]
      ],
      "B": [
       [
        0.2,
        1
       ]
      ]
     },
     "nota": "Após milho ou sorgo, elevar o N de plantio para 40 kg/ha."
    },
    "girassol": {
     "nome": "Girassol",
     "fonte": "Boletim 100, ed. 2022, item 3.8.8",
     "V2": 70,
     "Mgmin": 8,
     "prod": [
      "< 2,0 t/ha",
      "2,0–3,0 t/ha",
      "> 3,0 t/ha"
     ],
     "Npl": [
      10,
      20,
      30
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        80,
        100,
        120
       ],
       [
        50,
        70,
        80
       ],
       [
        20,
        30,
        40
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        60,
        80,
        100
       ],
       [
        40,
        60,
        80
       ],
       [
        20,
        30,
        40
       ]
      ]
     },
     "NcobFix": [
      50,
      50,
      50
     ],
     "Ksulco": 50,
     "Pzero": {
      "acima": 80,
      "dose": 20
     },
     "Kzero": 6,
     "S": {
      "fix": [
       20,
       20,
       20
      ]
     },
     "micro": {
      "B": [
       [
        0.2,
        2
       ],
       [
        0.61,
        1
       ]
      ]
     }
    },
    "verdes": {
     "nome": "Adubos verdes (crotalária, mucuna, guandu…)",
     "fonte": "Boletim 100, ed. 2022, item 3.8.10",
     "V2": 70,
     "Mgmin": 8,
     "prod": [
      "Baixa",
      "Média",
      "Alta"
     ],
     "Npl": [
      0,
      0,
      0
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        40,
        60,
        80
       ],
       [
        20,
        40,
        60
       ],
       [
        20,
        20,
        20
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        40,
        60,
        80
       ],
       [
        20,
        40,
        60
       ],
       [
        0,
        0,
        0
       ]
      ]
     },
     "nota": "Com P e K médios ou altos, a adubação pode ser dispensada."
    },
    "mandMesa": {
     "nome": "Mandioca de mesa",
     "fonte": "Boletim 100, ed. 2022, item 3.10.4",
     "V2": 60,
     "Mgmin": 6,
     "prod": [
      "< 25 t/ha",
      "25–30 t/ha",
      "> 30 t/ha"
     ],
     "Npl": [
      10,
      10,
      10
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        80,
        120,
        140
       ],
       [
        60,
        100,
        120
       ],
       [
        40,
        60,
        80
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        40,
        60,
        80
       ],
       [
        30,
        40,
        60
       ],
       [
        10,
        20,
        30
       ]
      ]
     },
     "NcobFix": [
      10,
      20,
      30
     ],
     "NredMO": {
      "acima": 20,
      "fator": 0.7
     },
     "Kcob": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        50,
        70,
        90
       ],
       [
        40,
        60,
        70
       ],
       [
        30,
        50,
        60
       ]
      ]
     },
     "Ksulco": 60,
     "micro": {
      "Zn": [
       [
        0.7,
        4
       ]
      ]
     },
     "nota": "Cobertura aos 60–90 dias (plantio de verão) ou 90–120 dias (inverno). Zn 0,70–1,50 mg/dm³: 3 kg/ha de sulfato de zinco; acima de 1,5: 2 kg/ha. Calagem alta pode piorar o cozimento. Esterco: 6–12 t/ha bovino ou 3–6 t/ha de cama de frango."
    },
    "mandInd": {
     "nome": "Mandioca para indústria (1 ciclo)",
     "fonte": "Boletim 100, ed. 2022, item 3.10.5",
     "V2": 60,
     "Mgmin": 6,
     "prod": [
      "< 20 t/ha",
      "20–30 t/ha",
      "> 30 t/ha"
     ],
     "Npl": [
      10,
      10,
      10
     ],
     "P": {
      "lt": [
       16,
       41
      ],
      "v": [
       [
        70,
        80,
        100
       ],
       [
        55,
        65,
        80
       ],
       [
        40,
        50,
        60
       ]
      ]
     },
     "K": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        30,
        50,
        70
       ],
       [
        20,
        40,
        60
       ],
       [
        10,
        30,
        50
       ]
      ]
     },
     "NcobFix": [
      10,
      20,
      40
     ],
     "NredMO": {
      "acima": 20,
      "fator": 0.7
     },
     "Kcob": {
      "lt": [
       1.6,
       3.05
      ],
      "v": [
       [
        20,
        25,
        30
       ],
       [
        10,
        15,
        20
       ],
       [
        10,
        10,
        15
       ]
      ]
     },
     "Ksulco": 60,
     "micro": {
      "Zn": [
       [
        0.7,
        4
       ]
      ]
     },
     "nota": "Cobertura aos 30–60 dias após a brotação. Reduzir o N em 30% em solos de textura média/argilosa ou M.O. > 20. Para 2 ciclos (16–24 meses) há uma tabela extra de P e K no 2º ciclo."
    },
    "canaPl": {
     "nome": "Cana-de-açúcar – cana-planta",
     "fonte": "Boletim 100, ed. 2022, item 3.3.6",
     "V2": 70,
     "Mgmin": 8,
     "calMin100": 1.5,
     "prod": [
      "< 100 t/ha",
      "100–130 t/ha",
      "130–150 t/ha",
      "150–170 t/ha",
      "> 170 t/ha"
     ],
     "Npl": [
      30,
      30,
      30,
      30,
      30
     ],
     "P": {
      "lt": [
       7,
       16,
       41
      ],
      "v": [
       [
        180,
        180,
        200,
        200,
        200
       ],
       [
        140,
        160,
        180,
        180,
        200
       ],
       [
        80,
        100,
        120,
        140,
        140
       ],
       [
        40,
        60,
        80,
        100,
        100
       ]
      ]
     },
     "K": {
      "lt": [
       0.8,
       1.6,
       3.05
      ],
      "v": [
       [
        140,
        160,
        180,
        200,
        220
       ],
       [
        120,
        140,
        160,
        180,
        200
       ],
       [
        100,
        120,
        140,
        160,
        180
       ],
       [
        60,
        80,
        100,
        120,
        120
       ]
      ]
     },
     "NcobFix": [
      30,
      30,
      60,
      60,
      60
     ],
     "Ksulco": 80,
     "Kzero": 6,
     "fosfCana": true,
     "gesso": "cana",
     "Scana": true,
     "micro": {
      "B": [
       [
        0.2,
        2
       ],
       [
        0.61,
        1
       ]
      ],
      "Cu": [
       [
        0.3,
        5
       ]
      ],
      "Mn": [
       [
        1.2,
        5
       ]
      ],
      "Zn": [
       [
        0.6,
        10
       ],
       [
        1.21,
        5
       ],
       [
        999,
        2
       ]
      ]
     },
     "microLim": {
      "Mn": [
       1.2,
       5
      ]
     },
     "nota": "Amostragem 0–25 cm (calagem/adubação) e 25–50 cm (gesso e S). Cobertura de 30–60 kg/ha de N na quebra-lombo. Mo: 0,6 kg/ha no sulco. Se a camada 25–50 cm tiver V < 50% ou m > 30%, some a calagem para elevar V a 70% nessa camada."
    },
    "canaSoca": {
     "nome": "Cana-de-açúcar – soqueira",
     "fonte": "Boletim 100, ed. 2022, item 3.3.7",
     "V2": 70,
     "Mgmin": 8,
     "unica": true,
     "prod": [
      "< 80 t/ha",
      "80–100 t/ha",
      "100–120 t/ha",
      "120–140 t/ha",
      "> 140 t/ha"
     ],
     "Npl": [
      80,
      100,
      120,
      140,
      160
     ],
     "P": {
      "lt": [
       7,
       16,
       41
      ],
      "v": [
       [
        40,
        40,
        60,
        60,
        60
       ],
       [
        20,
        20,
        40,
        40,
        40
       ],
       [
        0,
        0,
        30,
        30,
        30
       ],
       [
        0,
        0,
        0,
        0,
        0
       ]
      ]
     },
     "K": {
      "lt": [
       0.8,
       1.6,
       3.05
      ],
      "v": [
       [
        100,
        140,
        160,
        180,
        200
       ],
       [
        80,
        100,
        120,
        140,
        160
       ],
       [
        60,
        80,
        100,
        120,
        140
       ],
       [
        40,
        60,
        80,
        100,
        100
       ]
      ]
     },
     "Kzero": 6,
     "gesso": "cana",
     "nota": "Use a maior entre a produtividade do ciclo anterior e a esperada. Doses para cana crua. Desconte 70% do N e 100% do K da vinhaça. 10 t/ha de palha ≈ 70 kg/ha de K₂O que podem ser descontados."
    },
    "pastoFI": {
     "nome": "Pastagem – formação, gramíneas Grupo I (Mombaça, Tanzânia, Marandu, Tifton…)",
     "fonte": "Boletim 100, ed. 2022, item 3.12",
     "V2": 70,
     "Mgmin": 9,
     "prod": [
      "—"
     ],
     "Npl": [
      0
     ],
     "P": {
      "lt": [
       7,
       16,
       41
      ],
      "v": [
       [
        100
       ],
       [
        70
       ],
       [
        40
       ],
       [
        0
       ]
      ]
     },
     "K": {
      "lt": [
       0.8,
       1.6,
       3.05
      ],
      "v": [
       [
        60
       ],
       [
        40
       ],
       [
        0
       ],
       [
        0
       ]
      ]
     },
     "NcobFix": [
      40
     ],
     "S": {
      "fix": [
       20
      ]
     },
     "micro": {
      "Zn": [
       [
        0.6,
        3
       ],
       [
        1.21,
        2
       ]
      ]
     },
     "gesso": "pasto",
     "nota": "N de cobertura (30–40 dias) só se houver sintoma de deficiência."
    },
    "pastoF2": {
     "nome": "Pastagem – formação, gramíneas Grupos II e III (Piatã, decumbens, humidicola…)",
     "fonte": "Boletim 100, ed. 2022, item 3.12",
     "V2": 50,
     "Mgmin": 6,
     "prod": [
      "—"
     ],
     "Npl": [
      0
     ],
     "P": {
      "lt": [
       7,
       16,
       41
      ],
      "v": [
       [
        80
       ],
       [
        60
       ],
       [
        40
       ],
       [
        0
       ]
      ]
     },
     "K": {
      "lt": [
       0.8,
       1.6,
       3.05
      ],
      "v": [
       [
        50
       ],
       [
        30
       ],
       [
        0
       ],
       [
        0
       ]
      ]
     },
     "NcobFix": [
      40
     ],
     "S": {
      "fix": [
       20
      ]
     },
     "micro": {
      "Zn": [
       [
        0.6,
        2
       ]
      ]
     },
     "gesso": "pasto",
     "nota": "N de cobertura (30–40 dias) só se houver sintoma de deficiência."
    },
    "pastoMI": {
     "nome": "Pastagem – manutenção, Grupo I (por ano)",
     "fonte": "Boletim 100, ed. 2022, item 3.12",
     "V2": 70,
     "Mgmin": 9,
     "unica": true,
     "prod": [
      "—"
     ],
     "Npl": [
      120
     ],
     "P": {
      "lt": [
       7,
       16,
       41
      ],
      "v": [
       [
        50
       ],
       [
        40
       ],
       [
        20
       ],
       [
        0
       ]
      ]
     },
     "K": {
      "lt": [
       0.8,
       1.6,
       3.05
      ],
      "v": [
       [
        50
       ],
       [
        40
       ],
       [
        30
       ],
       [
        0
       ]
      ]
     },
     "S": {
      "fix": [
       20
      ]
     },
     "gesso": "pasto",
     "nota": "Em pasto estabelecido, o V desejado pode ser reduzido em 10–20%. Aplicar PK e 60% do N no início das águas, após rebaixar o pasto; o restante em fevereiro–março."
    },
    "pastoM2": {
     "nome": "Pastagem – manutenção, Grupos II e III (por ano)",
     "fonte": "Boletim 100, ed. 2022, item 3.12",
     "V2": 50,
     "Mgmin": 6,
     "unica": true,
     "prod": [
      "—"
     ],
     "Npl": [
      80
     ],
     "P": {
      "lt": [
       7,
       16,
       41
      ],
      "v": [
       [
        40
       ],
       [
        30
       ],
       [
        20
       ],
       [
        0
       ]
      ]
     },
     "K": {
      "lt": [
       0.8,
       1.6,
       3.05
      ],
      "v": [
       [
        40
       ],
       [
        30
       ],
       [
        20
       ],
       [
        0
       ]
      ]
     },
     "S": {
      "fix": [
       20
      ]
     },
     "gesso": "pasto",
     "nota": "Para U. decumbens e U. humidicola as doses de NPK podem ser reduzidas em 30%."
    }
   }
  },
  "mg": {
   "nome": "5ª Aproximação (CFSEMG, 1999)",
   "crops": {
    "soja": {
     "nome": "Soja",
     "fonte": "5ª Aproximação MG, item 18.4.15",
     "V2": 50,
     "mt": 20,
     "X": 2,
     "prod": [
      "2,5–3,0 t/ha"
     ],
     "Npl": [
      0
     ],
     "P": {
      "v": [
       [
        120
       ],
       [
        80
       ],
       [
        40
       ]
      ]
     },
     "K": {
      "v": [
       [
        120
       ],
       [
        80
       ],
       [
        40
       ]
      ]
     },
     "Ksulco": 50,
     "nota": "Sem N com boa inoculação. S: 30 kg/ha no sulco se houver deficiência (fórmulas concentradas sem S). Pode suspender o P temporariamente com P acima de 30 (textura arenosa/média) ou 12 mg/dm³ (argilosa)."
    },
    "milho": {
     "nome": "Milho grão",
     "fonte": "5ª Aproximação MG, item 18.4.13.1",
     "V2": 60,
     "mt": 15,
     "X": 2,
     "maxCal": 6,
     "prod": [
      "4–6 t/ha",
      "6–8 t/ha",
      "> 8 t/ha"
     ],
     "Npl": [
      20,
      20,
      20
     ],
     "Ncob": {
      "alta": [
       60,
       100,
       140
      ],
      "media": [
       60,
       100,
       140
      ],
      "baixa": [
       40,
       80,
       120
      ]
     },
     "P": {
      "v": [
       [
        80,
        100,
        120
       ],
       [
        60,
        80,
        100
       ],
       [
        30,
        50,
        70
       ]
      ]
     },
     "K": {
      "v": [
       [
        50,
        70,
        90
       ],
       [
        40,
        60,
        80
       ],
       [
        20,
        40,
        60
       ]
      ]
     },
     "KmetadeAcima": 80,
     "respNota": "Baixa: sucessão ou rotação com soja (desconta 20 kg/ha de N da cobertura).",
     "nota": "Plantio direto: N de plantio 30 kg/ha. Solo deficiente em Zn: 1–2 kg/ha. Com adubos concentrados, 30 kg/ha de S. Relação Ca:Mg abaixo de 3:1 prejudica o milho."
    },
    "sorgo": {
     "nome": "Sorgo granífero",
     "fonte": "5ª Aproximação MG, item 18.4.16.1",
     "V2": 60,
     "mt": 15,
     "X": 2,
     "prod": [
      "4–6 t/ha",
      "6–8 t/ha"
     ],
     "Npl": [
      15,
      15
     ],
     "NcobFix": [
      40,
      80
     ],
     "P": {
      "v": [
       [
        70,
        80
       ],
       [
        50,
        60
       ],
       [
        30,
        40
       ]
      ]
     },
     "K": {
      "v": [
       [
        50,
        70
       ],
       [
        40,
        60
       ],
       [
        20,
        40
       ]
      ]
     }
    },
    "feijao": {
     "nome": "Feijão",
     "fonte": "5ª Aproximação MG, item 18.4.8",
     "V2": 50,
     "mt": 20,
     "X": 2,
     "prod": [
      "NT1 – até 1,2 t/ha",
      "NT2 – 1,2 a 1,8 t/ha",
      "NT3 – 1,8 a 2,5 t/ha",
      "NT4 – acima de 2,5 t/ha"
     ],
     "Npl": [
      20,
      20,
      30,
      40
     ],
     "NcobFix": [
      20,
      30,
      40,
      60
     ],
     "P": {
      "v": [
       [
        70,
        80,
        90,
        110
       ],
       [
        50,
        60,
        70,
        90
       ],
       [
        30,
        40,
        50,
        70
       ]
      ]
     },
     "K": {
      "v": [
       [
        30,
        30,
        40,
        50
       ],
       [
        20,
        20,
        30,
        40
       ],
       [
        20,
        20,
        20,
        20
       ]
      ]
     },
     "nota": "NT1: sementes catadas; NT2: sementes fiscalizadas e controle fitossanitário; NT3: + herbicida e irrigação; NT4: NT3 com mais adubo. Mo foliar 60 g/ha entre 15 e 25 DAE. Mg ou S baixos: 20 kg/ha. B e Zn deficientes: 1 kg/ha de B e 2–4 kg/ha de Zn."
    },
    "mandioca": {
     "nome": "Mandioca",
     "fonte": "5ª Aproximação MG, item 18.4.12",
     "V2": 40,
     "mt": 30,
     "X": 1,
     "maxCal": 2,
     "prod": [
      "20 t/ha"
     ],
     "Npl": [
      0
     ],
     "NcobFix": [
      40
     ],
     "mandMG": true,
     "P": {
      "v": [
       [
        80
       ],
       [
        40
       ],
       [
        20
       ],
       [
        0
       ]
      ]
     },
     "K": {
      "v": [
       [
        60
       ],
       [
        40
       ],
       [
        20
       ],
       [
        0
       ]
      ]
     },
     "nota": "Não ultrapassar 2 t/ha de calcário. N em cobertura 30–60 dias após a brotação. Zn deficiente: 5 kg/ha. A mandioca responde mais ao P do que ao N e K."
    },
    "canaPl": {
     "nome": "Cana-de-açúcar – cana-planta",
     "fonte": "5ª Aproximação MG, item 18.4.5",
     "V2": 60,
     "mt": 30,
     "X": 3.5,
     "maxCal": 10,
     "canaMG": true,
     "prod": [
      "< 120 t/ha",
      "> 120 t/ha"
     ],
     "Npl": [
      0,
      0
     ],
     "NcobFix": [
      0,
      0
     ],
     "P": {
      "v": [
       [
        120,
        150
       ],
       [
        80,
        100
       ],
       [
        40,
        50
       ]
      ]
     },
     "K": {
      "v": [
       [
        120,
        160
       ],
       [
        90,
        120
       ],
       [
        60,
        80
       ]
      ]
     },
     "Ksulco": 90,
     "KzeroMg": 150,
     "nota": "N em cobertura: até 60 kg/ha conforme histórico (solos de primeiro cultivo, cultivo mínimo, cana crua, pouca M.O.). Áreas carentes em S: no mínimo 30 kg/ha de S."
    },
    "canaSoca": {
     "nome": "Cana-de-açúcar – soqueira",
     "fonte": "5ª Aproximação MG, item 18.4.5",
     "V2": 60,
     "mt": 30,
     "X": 3.5,
     "maxCal": 10,
     "canaMG": true,
     "unica": true,
     "prod": [
      "< 60 t/ha",
      "60–80 t/ha",
      "> 80 t/ha"
     ],
     "Npl": [
      60,
      80,
      100
     ],
     "P": {
      "v": [
       [
        40,
        40,
        40
       ],
       [
        0,
        0,
        0
       ],
       [
        0,
        0,
        0
       ]
      ]
     },
     "K": {
      "v": [
       [
        80,
        110,
        140
       ],
       [
        40,
        70,
        100
       ],
       [
        0,
        30,
        60
       ]
      ]
     },
     "KzeroMg": 150,
     "nota": "Em áreas com vinhaça, dispensar o K; N só se a produtividade esperada passar de 80 t/ha (40 kg/ha)."
    }
   }
  },
  "cerrado": {
   "nome": "Embrapa Cerrados",
   "crops": {
    "soja": {
     "nome": "Soja",
     "fonte": "Embrapa Soja (2020) cap. 7; Sousa et al. (2016); Vilela et al. (2004); mt e X da 5ª Aproximação",
     "V2": 50,
     "X": 2,
     "mt": 20,
     "prod": 3.6,
     "Pt": {
      "ate": 15,
      "alto": 10,
      "muitoAlto": 0
     },
     "Kt": 20,
     "Npl": 0,
     "NcobFix": 0,
     "gesso": 50,
     "nota": "A Embrapa Soja indica V2 = 60% para Mato Grosso do Sul e 50% para os demais solos de Cerrado. N vem da inoculação; aplique 2–3 g/ha de Co e 12–25 g/ha de Mo."
    },
    "milho": {
     "nome": "Milho para grãos",
     "fonte": "Classes e corretiva de P/K: Embrapa Cerrados; manutenção pela exportação; N: Boletim 100 (2022)",
     "V2": 50,
     "X": 2,
     "mt": 15,
     "prod": 8,
     "Pt": {
      "ate": 10,
      "alto": 7,
      "muitoAlto": 0
     },
     "Kt": 6,
     "Nref": "milho",
     "gesso": 50,
     "aviso": "Manutenção de P e K estimada pela exportação nos grãos. Para milho, confira também a tabela da 5ª Aproximação."
    },
    "feijao": {
     "nome": "Feijão",
     "fonte": "Classes e corretiva de P/K: Embrapa Cerrados; manutenção pela exportação",
     "V2": 50,
     "X": 2,
     "mt": 20,
     "prod": 2.5,
     "Pt": {
      "ate": 10,
      "alto": 7,
      "muitoAlto": 0
     },
     "Kt": 23,
     "Npl": 20,
     "NcobFix": 40,
     "gesso": 50,
     "aviso": "Manutenção de P e K pela exportação nos grãos e N de referência. Para feijão, a 5ª Aproximação tem tabela própria."
    }
   },
   "PresLims": [
    5,
    8,
    14,
    20,
    35
   ],
   "PmehLims": [
    [
     6,
     12,
     18,
     25,
     40
    ],
    [
     5,
     10,
     15,
     20,
     35
    ],
    [
     3,
     5,
     8,
     12,
     18
    ],
    [
     2,
     3,
     4,
     6,
     9
    ]
   ],
   "bandas": [
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
    60,
    65,
    999
   ],
   "NCmeh": [
    20,
    18,
    17,
    15,
    14,
    13,
    11,
    10,
    8,
    7,
    5,
    4
   ],
   "CTPmeh": [
    5,
    6,
    7,
    9,
    11,
    15,
    18,
    23,
    29,
    37,
    54,
    70
   ],
   "NCres": 15,
   "CTPres": [
    6,
    7,
    8,
    9,
    10,
    12,
    13,
    14,
    15,
    16,
    17,
    19
   ]
  }
 },
 "MGP": {
  "arg": [
   [
    60,
    [
     2.7,
     5.4,
     8,
     12
    ]
   ],
   [
    35,
    [
     4,
     8,
     12,
     18
    ]
   ],
   [
    15,
    [
     6.6,
     12,
     20,
     30
    ]
   ],
   [
    0,
    [
     10,
     20,
     30,
     45
    ]
   ]
  ],
  "K": [
   15,
   40,
   70,
   120
  ]
 },
 "MICRO": {
  "b100": {
   "fonte": "DTPA / água quente (Boletim 100, 2022 – anuais)",
   "lim": {
    "B": [
     0.2,
     0.6
    ],
    "Cu": [
     0.3,
     0.8
    ],
    "Fe": [
     5,
     12
    ],
    "Mn": [
     1.5,
     5
    ],
    "Zn": [
     0.6,
     1.2
    ]
   }
  },
  "cerrado": {
   "fonte": "Mehlich-1 / água quente (Galrão, 2004)",
   "lim": {
    "B": [
     0.3,
     0.5
    ],
    "Cu": [
     0.5,
     0.8
    ],
    "Mn": [
     2,
     5
    ],
    "Zn": [
     1.1,
     1.6
    ]
   },
   "dose": {
    "B": [
     2,
     0.5
    ],
    "Cu": [
     2,
     0.5
    ],
    "Mn": [
     6,
     1.5
    ],
    "Zn": [
     6,
     1.5
    ]
   }
  }
 }
});
