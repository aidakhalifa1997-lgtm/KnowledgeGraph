from core.text import content_terms, fold_accents, light_stem, normalize_key, normalize_with_map, split_sentences
from ingestion.chunking import chunk_document, contextual_text
from ingestion.cleaning import clean_page, prepare_pages, remove_repeated_lines
from ingestion.metadata import extract_metadata, infer_doc_type, parse_date, parse_diffusion


def test_normalize_with_map_preserves_original_offsets():
    text = "Le Pôle Sécurité des SI"
    normalized, mapping = normalize_with_map(text)
    start = normalized.index("pole securite")
    end = start + len("pole securite")
    assert text[mapping[start]: mapping[end - 1] + 1] == "Pôle Sécurité"


def test_split_sentences_keeps_abbreviations():
    sentences = split_sentences("Validé par M. Karim El Fassi. Mme Salma Idrissi préside. Voir cf. PRC-KYC-001.")
    assert sentences == ["Validé par M. Karim El Fassi.", "Mme Salma Idrissi préside.", "Voir cf. PRC-KYC-001."]


def test_content_terms_drop_stopwords_and_interrogatives():
    terms = content_terms("Combien de clients la banque compte-t-elle ?")
    assert "compte" in terms and "combien" not in terms and "compte-t-elle" not in terms


def test_stemming_groups_inflections():
    assert light_stem("refusée")[:6] == light_stem("refus")[:6]
    assert light_stem("délégué")[:6] != light_stem("délégation")[:6]


def test_normalize_key_and_accents():
    assert normalize_key("  L’Équipe   Projet ") == "l'equipe projet"
    assert fold_accents("Réclam'Online") == "Reclam'Online"


def test_repeated_headers_removed_and_footer_template_removed():
    pages = ["Entête commun\nContenu A", "Entête commun\nContenu B", "Entête commun\nContenu C"]
    assert all("Entête commun" not in p for p in remove_repeated_lines(pages))
    assert "Interne" not in clean_page("PRC-KYC-001 - v1.0 - Interne\nPage 2\nTexte utile.", join_wrapped_lines=True)


def test_pdf_line_joining_and_bullets():
    raw = "La présente procédure définit les règles applicables lors de l'entrée en\nrelation avec un client.\n•\nPremier point de liste"
    cleaned = clean_page(raw, join_wrapped_lines=True)
    assert "l'entrée en relation avec un client." in cleaned
    assert "- Premier point de liste" in cleaned


def test_cartouche_parsing_and_restricted_diffusion():
    text = "\n".join([
        "ORIZIA BANQUE - document fictif", "Référence : PRC-RSK-006", "Version : 2.0", "Date : 12/05/2025",
        "Direction propriétaire : Pôle Risques Opérationnels", "Rédacteur : Sanaa Lahlou",
        "Classification : Confidentiel", "Diffusion : Restreinte : DRISK, DSI, DG", "# Titre", "Corps du texte.",
        "Rédacteur : quelqu'un d'autre (ligne du corps)"])
    meta, body = extract_metadata(prepare_pages([text])[0], {}, "x.pdf")
    assert meta.reference == "PRC-RSK-006" and meta.version == "2.0" and str(meta.doc_date) == "2025-05-12"
    assert meta.classification == "Confidentiel" and meta.diffusion == ["DRISK", "DSI", "DG"]
    assert meta.author_name == "Sanaa Lahlou", "une ligne du corps ne doit pas écraser le cartouche"
    assert "Référence" not in body and "Rédacteur : quelqu'un" in body
    assert meta.doc_type == "procedure"


def test_metadata_helpers():
    assert str(parse_date("16 juin 2025")) == "2025-06-16"
    assert parse_diffusion("Tous collaborateurs") == ["ALL"]
    assert infer_doc_type("CR-CONF-2025-03", None) == "compte_rendu"


def test_chunking_respects_sections_and_size():
    pages = ["## 1. Objet\n" + ("Phrase de test assez longue pour remplir. " * 30) + "\n## 2. Périmètre\nTexte court."]
    chunks = chunk_document(pages, target_chars=400, max_chars=600)
    assert len(chunks) >= 3
    assert chunks[-1].section == "2. Périmètre"
    assert all(len(c.text) <= 700 for c in chunks)
    assert contextual_text("Titre", "Section", "texte").startswith("Titre\nSection")


def test_numbered_list_item_is_not_a_heading():
    chunks = chunk_document(["## Objectifs\n1. Mettre à jour la procédure PRC-RSK-006 (version 2.0).\n2. Former les équipes."])
    assert "Mettre à jour la procédure" in chunks[0].text
