class Mother(object):
    def __init__(self):
        self._haircolor = "Brown"

class Child(Mother):
    def __init__(self): 
        super().__init__()
        print(self._haircolor)
    def print_haircolor(self):
        print(self._haircolor)

c = Child()
c.print_haircolor()
