import imageio
import numpy as np


def compare(expected_filename: str, submitted_filename: str):
    from PIL import Image
    expected_img = np.array(Image.open(expected_filename))
    submitted_img = np.array(Image.open(submitted_filename))

    diff_img = expected_img - submitted_img

    #imageio.imwrite("s.png", submitted_img)

    return diff_img, expected_img


def colorize_diff(expected_img, diff_img):
    '''
    TODO: Overlay of diff over expected image.
    '''
    print(diff_img)
    print(diff_img.min())
    print(diff_img.max())

    colorized_diff_img = np.zeros(diff_img.shape, diff_img.dtype)
    nz_indices = np.nonzero(diff_img)
    np.put(colorized_diff_img, nz_indices, [255, 0, 0, 255])

    print(nz_indices)
    #np.where(colorize_diff == [0, 0, 0], colorized_diff_img, [255, 0, 0])

    for i, j in zip(nz_indices[0], nz_indices[1]):
        print(i, j)
        colorized_diff_img[i, j] = [255, 0, 0, 255]

    print(colorized_diff_img.min())
    print(colorized_diff_img.max())

    #print(colorized_diff_img[90, 410])

    return colorized_diff_img


def run_test():
    expected_filename = 'tests/image/lena_expected.png'
    submitted_filename = 'tests/image/lena_submitted.png'

    diff_img, expected_img = compare(expected_filename, submitted_filename)
    color_diff_img = colorize_diff(expected_img, diff_img)

    imageio.imwrite('color_diff.png', color_diff_img)


def main():
    run_test()


if __name__ == '__main__':
    main()