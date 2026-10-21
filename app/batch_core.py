"""Parsing and controlled sequential execution, without cloud dependencies."""
import re
import sys


def parse_articles(value):
    if not isinstance(value,str) or not value.strip() or len(value)>200:
        raise ValueError('Indiquer des articles, par exemple 1-3,22-28.')
    result=set()
    for token in value.split(','):
        token=token.strip()
        if not re.fullmatch(r'\d{1,2}(?:-\d{1,2})?',token):
            raise ValueError('Format attendu : 1-3,22-28.')
        bounds=[int(v) for v in token.split('-')]
        first,last=(bounds[0],bounds[-1])
        if not 1<=first<=last<=28:raise ValueError('Articles autorisés : 1 à 28 ; intervalles croissants.')
        result.update(range(first,last+1))
    return sorted(result)


def execute_batch(articles,runner):
    completed=[]
    for article in articles:
        # Argument array, no shell interpolation. Existing extractor owns API
        # calls, exact-input deduplication and saving results.
        result=runner([sys.executable,'-m','app.extract','--article',str(article),'--execute'])
        completed.append((article,result.returncode))
        if result.returncode:
            break
    return completed
