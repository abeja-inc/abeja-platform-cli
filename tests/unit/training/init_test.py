from abejacli.training import is_valid_image_and_handler_pair


def test_is_valid_image_and_handler_pair():
    image = 'abeja-inc/all-cpu:18.10'
    handler = 'train:handler'
    assert is_valid_image_and_handler_pair(image, handler)

    image = 'abeja-inc/all-cpu:18.10'
    handler = 'train'
    assert not is_valid_image_and_handler_pair(image, handler)

    image = 'abeja-inc/all-cpu:20.02a'
    handler = 'train'
    assert is_valid_image_and_handler_pair(image, handler)

    image = 'abeja-inc/all-cpu:20.02a'
    handler = 'train:handler'
    assert is_valid_image_and_handler_pair(image, handler)
