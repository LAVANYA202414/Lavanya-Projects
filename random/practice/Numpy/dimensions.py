import numpy as np

# 0-D Arrays
a = np.array(42)
print(a)

# 1-D Arrays
b = np.array([1,2,3,4])
print(b )

# 2-D Arrays
c = np.array([[1,2,3,4],[5,6,7,8]])
print(c)

# 3-D Arrays
d = np.array([[[1,2,3],[4,5,6],[7,8,9]]])
print(d)


# Check Number of Dimensions?
# NumPy Arrays provides the ndim attribute that returns an integer that tells us how many dimensions the array have.

print(f"dimensions --> a: {a.ndim}, b: {b.ndim}, c: {c.ndim}, d: {d.ndim}")


# Higher Dimensional Arrays
# When the array is created, you can define the number of dimensions by using the ndim argument
array = np.array([1,2,3,4], ndmin = 6)
print(f"Array: {array}, and it's dimensions are {array.ndim}")