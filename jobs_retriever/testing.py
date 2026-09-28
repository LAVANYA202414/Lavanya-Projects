# numbers = [1,9,25,78,30]
# def second_largest(numbers):
#     new_list = list(set(numbers))
#     if len(new_list) < 2:
#         print("List should be of more than 2 numbers")

#     else:
#         print(new_list)
#         new_list.sort()
       
#         second_largest1 = new_list[-2]
#         print(second_largest1)

# obj1 = second_largest(numbers)






# number = 11
# def find_prime(number):
#     if number   :
#         print("Accepted")

#     else:
#         print("Not accepted")

# obj2 = find_prime(number)





# numbers = [1,9,25,78,30]
# def second_largest(numbers):
#     new_list = list(set(numbers))
#     if len(new_list) < 2:
#         print("List should be of more than 2 numbers")

#     else:
#         print(new_list)
#         new_list.sort()
#         total = new_list[-2] + new_list[-1]
#         print(total)

# obj1 = second_largest(numbers)




# s = "abc"
# t = "ahbgdc"


# class Solution:
#     def isSubsequence(self, s: str, t: str) -> bool:
#         for i in t:
#             # print(f"i: {i}")
#             for e in s:
#                 # print(f"e\ {e} i\{i}")
#                 if i == e:
#                     # print(f"e:{e}, i:{i}")
#                     # print("TRUE")
#                     return True
#                 # else:
#                     # print(f"e:{e}, i:{i}")
#                     # print("FALSE")
#                 # if e in t:
#                 #     print(f"printing e{e}")
#             return False
# obj = Solution()
# obj1 = obj.isSubsequence(s,t)










# class Solution:
    
#     def isSubsequence(self, s: str, t: str) -> bool:
#         final =True
#         if t == "" and s == "" or (s == ""):
#             return True
#         elif t == "":
#             return False
      
#         for i in range(len(s)):
#             for x in range(len(t)):
#                 if s[i] == t[x]:
#                     final = True
#                     break
#                 else:
#                     final = False
#             if final == False:
#                 break
        
#         return final


# s = "acb"
# t = "ahbgdc"
# a = ""
# obj = Solution.isSubsequence(a,s,t)

# print(obj)







# listing = [1,2,5,4,5,6,6,76,6]

# for i in range(len(listing)):
#     print(i)


# variable_array  = ["flow", "fly", "float"]
# listing = set()
# index = 0
# for single in variable_array:
#     for i in single:
#         if i in single:
#             if i == single[index]:
#                 listing.add(i)
#                 index += 1
# print(listing)


nums = [12,3,4,5,1,1,1,1,1]
nums = [1,2,3,4]
print(nums)