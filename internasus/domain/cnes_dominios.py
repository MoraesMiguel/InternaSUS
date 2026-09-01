"""
internasus.domain.cnes_dominios
Tabelas de domínio (código -> descrição) para campos de cadastro do CNES.

Fonte: dicionários de recodificação do pacote R `microdatasus` (rfsaldanha,
https://github.com/rfsaldanha/microdatasus, MIT license — pacote publicado e
usado academicamente para pré-processar microdados do DATASUS), copiados de
R/process_cnes.R. NAT_JUR também confere com a Tabela de Natureza Jurídica
oficial (IBGE/Concla + Receita Federal).

Achado de dado ao validar contra os parquets reais (ver Resumo_Evolucao.md):
* `ESFERA_A` é documentado classicamente como 1=Federal/2=Estadual/
  3=Municipal/4=Privada, mas na competência mais recente do nosso CNES (todas
  as 4 fontes) o campo vem **idêntico, byte a byte, a `TPGESTAO`** (valores
  'M'/'E', não '1'-'4'). Por isso ESFERA_A é decodificado aqui com o mesmo
  dicionário de TPGESTAO (`GESTAO`), não com o esquema numérico clássico —
  aplicar o esquema numérico não erraria (só não mapearia nada), mas seria
  enganoso por sugerir uma granularidade (Federal/Estadual/Municipal/Privada)
  que os dados não têm mais nesta exportação.
* `NAT_JUR = '4000'` é o código mais frequente na nossa base (~1/3 dos
  estabelecimentos) mas não existe na Tabela de Natureza Jurídica atual nem no
  dicionário do microdatasus — fica sem tradução (retorna None), não foi
  inventado um significado para ele.
* `TP_UNID = '16'` também aparece nos nossos dados sem entrada correspondente
  em nenhuma fonte consultada — mesmo tratamento (None).
"""

import pandas as pd

GESTAO = {
    "D": "Dupla",
    "E": "Estadual",
    "M": "Municipal",
    "Z": "Sem gestão",
    "S": "Sem gestão",
}

NIVEL_DEPENDENCIA = {
    "1": "Individual",
    "3": "Mantida",
}

CLIENTELA = {
    "0": "Fluxo de Clientela não exigido",
    "00": "Fluxo de Clientela não exigido",
    "1": "Atendimento de demanda espontânea",
    "01": "Atendimento de demanda espontânea",
    "2": "Atendimento de demanda referenciada",
    "02": "Atendimento de demanda referenciada",
    "3": "Atendimento de demanda espontânea e referenciada",
    "03": "Atendimento de demanda espontânea e referenciada",
}

TURNO_ATENDIMENTO = {
    "01": "Turnos intermitentes",
    "02": "Contínuo 24h/dia (Pl Sab Dom Fer)",
    "03": "Manhã / Tarde / Noite",
    "04": "Manhã",
    "05": "Tarde",
    "06": "Manhã / Tarde",
    "07": "Noite",
}

TIPO_UNIDADE = {
    "01": "Posto de saúde",
    "02": "Centro de saúde / Unidade básica",
    "04": "Policlínica",
    "05": "Hospital geral",
    "07": "Hospital Especializado",
    "09": "Pronto socorro de hospital geral (antigo)",
    "12": "Pronto socorro traumato-ortopédico (antigo)",
    "15": "Unidade mista",
    "20": "Pronto socorro geral",
    "21": "Pronto socorro especializado",
    "22": "Consultório isolado",
    "32": "Unidade móvel fluvial",
    "36": "Clínica / Centro de saúde de especialidade",
    "39": "Unidade de apoio diagnose e terapia (SADT isolado)",
    "40": "Unidade móvel terrestre",
    "42": "Unidade móvel de nível pré-hospitalar na área de urgência",
    "43": "Farmácia",
    "45": "Unidade de saúde da família",
    "50": "Unidade de vigilância em saúde",
    "60": "Cooperativa ou empresa de cessão de trabalhadores na saúde",
    "61": "Centro de parto normal - isolado",
    "62": "Hospital / Dia - Isolado",
    "63": "Unidade autorizadora",
    "64": "Central de regulação de serviços de saúde",
    "65": "Unidade de vigilância epidemiológica (antigo)",
    "66": "Unidade de vigilância sanitária (antigo)",
    "67": "Laboratório central de saúde pública LACEN",
    "68": "Central de gestão em saúde",
    "69": "Centro de atenção hemoterapia e/ou hematológica",
    "70": "Centro de atenção psicossocial",
    "71": "Centro de apoio à saúde da família",
    "72": "Unidade de atenção à saúde indígena",
    "73": "Pronto atendimento",
    "74": "Pólo academia da saúde",
    "75": "Telessaúde",
    "76": "Central de regulação médica das urgências",
    "77": "Serviço de atenção domiciliar isolado (Home care)",
    "78": "Unidade de atenção em regime residencial",
    "79": "Oficina ortopédica",
    "80": "Laboratório de saúde pública",
    "81": "Central de regulação do acesso",
    "82": "Central de notificação, captação e distribuição de órgãos estadual",
    "83": "Pólo de prevenção de doenças e agravos e promoção da saúde",
    "84": "Central de abastecimento",
    "85": "Centro de imunização",
}

NATUREZA_JURIDICA = {
    "0": "Não especificado ou ignorado",
    "1015": "Órgão Público do Poder Executivo Federal",
    "1023": "Órgão Público do Poder Executivo Estadual ou do Distrito Federal",
    "1031": "Órgão Público do Poder Executivo Municipal",
    "1040": "Órgão Público do Poder Legislativo Federal",
    "1058": "Órgão Público do Poder Legislativo Estadual ou do Distrito Federal",
    "1066": "Órgão Público do Poder Legislativo Municipal",
    "1074": "Órgão Público do Poder Judiciário Federal",
    "1082": "Órgão Público do Poder Judiciário Estadual",
    "1104": "Autarquia Federal",
    "1112": "Autarquia Estadual ou do Distrito Federal",
    "1120": "Autarquia Municipal",
    "1139": "Fundação Pública de Direito Público Federal",
    "1147": "Fundação Pública de Direito Público Estadual ou do Distrito Federal",
    "1155": "Fundação Pública de Direito Público Municipal",
    "1163": "Órgão Público Autônomo Federal",
    "1171": "Órgão Público Autônomo Estadual ou do Distrito Federal",
    "1180": "Órgão Público Autônomo Municipal",
    "1198": "Comissão Polinacional",
    "1201": "Fundo Público",
    "1210": "Consórcio Público de Direito Público (Associação Pública)",
    "1228": "Consórcio Público de Direito Privado",
    "1236": "Estado ou Distrito Federal",
    "1244": "Município",
    "1252": "Fundação Pública de Direito Privado Federal",
    "1260": "Fundação Pública de Direito Privado Estadual ou do Distrito Federal",
    "1279": "Fundação Pública de Direito Privado Municipal",
    "2011": "Empresa Pública",
    "2038": "Sociedade de Economia Mista",
    "2046": "Sociedade Anônima Aberta",
    "2054": "Sociedade Anônima Fechada",
    "2062": "Sociedade Empresária Limitada",
    "2070": "Sociedade Empresária em Nome Coletivo",
    "2089": "Sociedade Empresária em Comandita Simples",
    "2097": "Sociedade Empresária em Comandita por Ações",
    "2127": "Sociedade em Conta de Participação",
    "2135": "Empresário (Individual)",
    "2143": "Cooperativa",
    "2151": "Consórcio de Sociedades",
    "2160": "Grupo de Sociedades",
    "2178": "Estabelecimento, no Brasil, de Sociedade Estrangeira",
    "2194": "Estabelecimento, no Brasil, de Empresa Binacional Argentino-Brasileira",
    "2216": "Empresa Domiciliada no Exterior",
    "2224": "Clube/Fundo de Investimento",
    "2232": "Sociedade Simples Pura",
    "2240": "Sociedade Simples Limitada",
    "2259": "Sociedade Simples em Nome Coletivo",
    "2267": "Sociedade Simples em Comandita Simples",
    "2275": "Empresa Binacional",
    "2283": "Consórcio de Empregadores",
    "2291": "Consórcio Simples",
    "2305": "Empresa Individual de Responsabilidade Limitada (de Natureza Empresária)",
    "2313": "Empresa Individual de Responsabilidade Limitada (de Natureza Simples)",
    "2321": "Sociedade Unipessoal de Advogados",
    "2330": "Cooperativas de Consumo",
    "3034": "Serviço Notarial e Registral (Cartório)",
    "3069": "Fundação Privada",
    "3077": "Serviço Social Autônomo",
    "3085": "Condomínio Edilício",
    "3107": "Comissão de Conciliação Prévia",
    "3115": "Entidade de Mediação e Arbitragem",
    "3131": "Entidade Sindical",
    "3204": "Estabelecimento, no Brasil, de Fundação ou Associação Estrangeiras",
    "3212": "Fundação ou Associação Domiciliada no Exterior",
    "3220": "Organização Religiosa",
    "3239": "Comunidade Indígena",
    "3247": "Fundo Privado",
    "3255": "Órgão de Direção Nacional de Partido Político",
    "3263": "Órgão de Direção Regional de Partido Político",
    "3271": "Órgão de Direção Local de Partido Político",
    "3280": "Comitê Financeiro de Partido Político",
    "3298": "Frente Plebiscitária ou Referendária",
    "3301": "Organização Social (OS)",
    "3310": "Demais Condomínios",
    "3999": "Associação Privada",
    "4014": "Empresa Individual Imobiliária",
    "4022": "Segurado Especial",
    "4081": "Contribuinte Individual",
    "4090": "Candidato a Cargo Político Eletivo",
    "4111": "Leiloeiro",
    "4124": "Produtor Rural (Pessoa Física)",
    "5010": "Organização Internacional",
    "5029": "Representação Diplomática Estrangeira",
    "5037": "Outras Instituições Extraterritoriais",
}


TIPO_LEITO = {
    "1": "Cirúrgico",
    "2": "Clínico",
    "3": "Complementar",
    "4": "Obstétrico",
    "5": "Pediátrico",
    "6": "Outras Especialidades",
    "7": "Hospital Dia",
}
"""Fonte: CONASS (wiki.conass.org.br, 'Tabela de domínio CNES leito').
Nenhum tipo é "emergencial"/"urgência" — isso é caráter da internação
(SIH.CAR_INT: eletivo/urgência), um atributo do evento, não do leito."""

CODIGO_LEITO = {
    # Cirúrgico (TP_LEITO=1)
    "01": "Buco Maxilo Facial",
    "02": "Cardiologia",
    "03": "Cirurgia Geral",
    "04": "Endocrinologia",
    "05": "Gastroenterologia",
    "06": "Ginecologia",
    "08": "Nefrologia/Urologia",
    "09": "Neurocirurgia",
    "11": "Oftalmologia",
    "12": "Oncologia",
    "13": "Ortopedia/Traumatologia",
    "14": "Otorrinolaringologia",
    "15": "Plástica",
    "16": "Torácica",
    "67": "Transplante",
    "90": "Queimado Adulto",
    "91": "Queimado Pediátrico",
    # Clínico (TP_LEITO=2)
    "31": "AIDS",
    "32": "Cardiologia",
    "33": "Clínica Geral",
    "35": "Dermatologia",
    "36": "Geriatria",
    "37": "Hansenologia",
    "38": "Hematologia",
    "40": "Nefro/Urologia",
    "41": "Neonatologia",
    "42": "Neurologia",
    "44": "Oncologia",
    "46": "Pneumologia",
    "87": "Saúde Mental",
    "88": "Queimado Adulto",
    "89": "Queimado Pediátrico",
    # Obstétrico (TP_LEITO=4)
    "10": "Obstetrícia Cirúrgica",
    "43": "Obstetrícia Clínica",
    # Pediátrico (TP_LEITO=5)
    "45": "Pediatria Clínica",
    "68": "Pediatria Cirúrgica",
    # Outras Especialidades (TP_LEITO=6)
    "34": "Crônicos",
    "47": "Psiquiatria",
    "48": "Reabilitação",
    "49": "Pneumologia Sanitária",
    "84": "Acolhimento Noturno",
    # Hospital Dia (TP_LEITO=7)
    "07": "Cirúrgico/Diagnóstico/Terapêutico",
    "69": "AIDS",
    "71": "Intercorrência Pós-Transplante",
    "73": "Saúde Mental",
    # Complementar (TP_LEITO=3)
    "66": "Unidade Isolamento",
    "75": "UTI-A Tipo II",
    "76": "UTI-A Tipo III",
    "78": "UTI Pediátrica Tipo II",
    "79": "UTI Pediátrica Tipo III",
    "80": "UTI Neonatal Tipo I",
    "81": "UTI Neonatal Tipo II",
    "82": "UTI Neonatal Tipo III",
    "85": "UCO Tipo II",
    "86": "UCO Tipo III",
    "92": "Unidade de Cuidados Intermediários Neonatal Convencional",
    "93": "Unidade de Cuidados Intermediários Neonatal Canguru",
    "95": "UCI-A",
}
"""Fonte: CnesWeb (cnes2.datasus.gov.br/Mod_Ind_Tipo_Leito.asp), sistema oficial
do CNES. Códigos '65', '70', '72', '83', '94' aparecem nos nossos dados
(~0,6% das linhas de CNES-LT) mas não foram encontrados em nenhuma fonte
consultada — ficam sem tradução (None) em vez de um palpite."""


def decodificar(df: pd.DataFrame, coluna: str, dominio: dict[str, str]) -> pd.Series:
    """Mapeia `df[coluna]` (código bruto) para descrição via `dominio`.
    Códigos não encontrados no dicionário viram None (não são inventados) —
    imprime um aviso com os códigos não mapeados presentes nos dados."""
    descricoes = df[coluna].map(dominio)
    nao_mapeados = sorted(
        df.loc[df[coluna].notna() & descricoes.isna(), coluna].unique().tolist()
    )
    if nao_mapeados:
        print(f"[decodificar] '{coluna}': códigos sem tradução em domínio -> {nao_mapeados}")
    return descricoes
