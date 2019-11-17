def check(result, sandbox):
    result['processed'] = True
    return result['stdout'] == 'test 123456'
