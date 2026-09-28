import numpy as np

# Iterating Arrays
array = np.array([[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]])
for arr in array:
    print(arr)
    for ar in arr:
        print(ar)
        for a in ar:
            print(a)


# Iterating Arrays Using nditer()
# The function nditer() is a helping function that can be used from very basic to very advanced iterations. It solves some basic issues which we face in iteration, lets go through it with examples.
array = np.array([[[1,2], [3,4]], [[5,6], [7,8]]])
for arr in np.nditer(array):
    print(arr)