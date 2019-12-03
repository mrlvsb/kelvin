def check(result, sandbox):
    result['processed'] = True
    return result['stdout'].read() == 'test 123456'
