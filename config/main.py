def handler(iter, context):
    for line in iter:
        if 'total_without_tax' not in line:
            raise context.exceptions.InvalidInput('total_without_tax not in the request')
        total_without_tax = line['total_without_tax']
        total = total_without_tax * 1.08
        yield {'total': total}
