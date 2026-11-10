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
