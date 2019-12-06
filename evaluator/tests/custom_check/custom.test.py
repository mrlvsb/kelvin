def check(result, sandbox):
    result['processed'] = True
    return result['stdout']['actual'].read() == 'test 123456'
