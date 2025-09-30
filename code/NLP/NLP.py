import spacy
nlp = spacy.load("en_core_web_sm")
def analyze_word(sentence, target_word):
    doc = nlp(sentence)
    for token in doc:
        if token.text.lower() == target_word.lower():
            print(f"单词: {token.text}")
            print(f"词性: {token.pos_}")  # 例如 VERB, ADJ, NOUN...
            print(f"词形还原: {token.lemma_}")  # 原型
            if token.pos_ == "VERB":
                return token.lemma_  # 查原型
            else:
                return token.text  # 查现在的形式
    return None