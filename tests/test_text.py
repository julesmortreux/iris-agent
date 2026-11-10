from backend.text import SCOPE_REPLY, clean, within_scope


def test_clean_retire_emojis_tirets_longs_et_titres():
    assert clean('### Bonjour \U0001F600') == 'Bonjour'
    assert clean('Voici des profils — triés') == 'Voici des profils, triés'


def test_clean_retire_les_lignes_qui_imitent_une_fiche():
    text = 'Voici des profils.\n**Jean Dupont**\nAmené par : Paul\n[LinkedIn](https://linkedin.com/in/x)'
    assert clean(text) == 'Voici des profils.'


def test_within_scope_remplace_les_promesses_hors_perimetre():
    assert within_scope('Je peux rédiger votre CV.') == SCOPE_REPLY
    assert within_scope('Je peux :\n- chercher\n- conseiller\n- écrire') == SCOPE_REPLY
    assert within_scope('Bonjour, je recherche des contacts dirigeants.') != SCOPE_REPLY


def test_requested_count():
    from backend.text import requested_count
    assert requested_count('donne-moi 3 contacts chez Airbus') == 3
    assert requested_count('trois profils dans la banque') == 3
    assert requested_count('deux autres dirigeants') == 2
    assert requested_count('un seul contact chez LVMH') == 1
    assert requested_count('un CFO chez Airbus') is None          # « un » est un article
    assert requested_count('un dirigeant dans la tech') is None
    assert requested_count('des contacts chez Total') is None


def test_fix_count_claims():
    from backend.text import fix_count_claims
    assert fix_count_claims('Voici 8 contacts influents.', 7) == 'Voici 7 contacts influents.'
    assert fix_count_claims('Voici trois dirigeants.', 2) == 'Voici 2 dirigeants.'
    assert fix_count_claims('Voici 7 contacts.', 7) == 'Voici 7 contacts.'
    assert fix_count_claims('Voici un profil et 5 contacts.', 5) == 'Voici un profil et 5 contacts.'
