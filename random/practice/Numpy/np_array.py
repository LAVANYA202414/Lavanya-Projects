import numpy as np

# Numpy = Numerical Python
# Create a NumPy ndarray Object

array = np.array([1,2,3,4])

print(array)
print(type(array))


# Checking Numpy version
print(np.__version__)


# Indexing
array = np.array([1,2,3,4,5,6,7,8,9,0])
print(array[8])

arr = np.array([[1,2,3,4,5], [6,7,8,9,10]])
print('2nd element on 1st row: ', arr[1, 4])


# Check if Array Owns its Data
array = np.array([2,4,6,8,0])
x = array.copy()
y = array.view()

print(x.base)
print(y.base)


# Get the Shape of an Array --> returns tuple
array = np.array([[4,3,2,1], [1,2,3,4]])
print(array.shape)

array = np.array([1,2], ndmin = 6)
print(array)
print(array.shape)