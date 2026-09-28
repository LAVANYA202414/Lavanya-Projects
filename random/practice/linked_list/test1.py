class ListNode:
    def __init__(self,val=0,next=None):
        self.val = val
        self.next = next


def add_two_numbers(l1: ListNode, l2: ListNode) -> ListNode:






# FINDING THE MIDDLE OF THE LIST
# def find_middle(current: ListNode) -> ListNode:
#     # moves one step at a time
#     slow = current
#     # moves two step at a time
#     fast = current

#     # fast.next -> ensures there is a next node
#     while fast and fast.next:
#         slow = slow.next
#         fast = fast.next.next
#         return slow
# head = ListNode(10, ListNode(20, ListNode(30)))
# result = find_middle(head)
# print(f"Result1 => ", result.val)


# # REVERSING THE LIST
# def reverse_list(head: ListNode) -> ListNode:
#     prev = None
#     current = head

#     while current:
#         nxt = current.next #2
#         print("nxt: ", nxt)
#         current.next = prev
#         print("current.next: ", current.next)
#         prev = current
#         print("pre: ", prev)
#         current = nxt
#     return prev
# head = ListNode(1, ListNode(2, ListNode(3)))

