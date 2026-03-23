class FinnishMorphologyAnalyzer:
    """
    Integrates a Finnish morphological analyzer.
    In a full production environment, this would wrap uralicNLP, libvoikko, or an external API.
    For demonstration, it provides a basic structure and rudimentary heuristic fallback.
    """
    
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        # Attempt to load uralicNLP if available
        self.uralic_api = None
        if not use_mock:
            try:
                from uralicNLP import uralicApi
                self.uralic_api = uralicApi
            except ImportError:
                pass

    def get_genitive_singular(self, noun: str) -> str:
        if self.uralic_api:
            try:
                # Generates forms. +N+Sg+Gen
                forms = self.uralic_api.generate(noun + "+N+Sg+Gen", "fin")
                if forms:
                    return forms[0][0]
            except Exception:
                pass
        
        # Very rudimentary fallback heuristics for testing
        if noun.endswith('a') or noun.endswith('ä') or noun.endswith('o') or noun.endswith('ö') or noun.endswith('u') or noun.endswith('y'):
            return noun + "n"
        elif noun.endswith('e'):
            return noun[:-1] + "een"
        elif noun.endswith('nen'):
            return noun[:-3] + "sen"
        elif noun.endswith('i'):
            return noun[:-1] + "in" # Highly irregular in reality
            
        return noun + "n" # Default fallback

    def get_first_person_singular(self, verb: str) -> str:
        if self.uralic_api:
            try:
                # Generates forms. +V+Act+Ind+Prs+Sg1
                forms = self.uralic_api.generate(verb + "+V+Act+Ind+Prs+Sg1", "fin")
                if forms:
                    return forms[0][0]
            except Exception:
                pass
                
        # Very rudimentary fallback heuristics for testing
        if verb.endswith('aa') or verb.endswith('ää'):
            return verb[:-1] + "n"
        elif verb.endswith('ta') or verb.endswith('tä'):
            return verb[:-2] + "aan" # Actually depends on consonant gradation
        elif verb.endswith('da') or verb.endswith('dä'):
            return verb[:-2] + "an"
            
        return verb + "n" # Default fallback
