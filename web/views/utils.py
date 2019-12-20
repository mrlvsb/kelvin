def is_teacher(user):
    return user.groups.filter(name='teachers').exists()
