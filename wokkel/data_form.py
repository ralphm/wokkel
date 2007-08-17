# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

from twisted.words.xish import domish

NS_X_DATA = 'jabber:x:data'

class Field(domish.Element):
    def __init__(self, type='text-single', var=None, label=None,
                       value=None, values=[], options={}):
        domish.Element.__init__(self, (NS_X_DATA, 'field'))
        self['type'] = type
        if var is not None:
            self['var'] = var
        if label is not None:
            self['label'] = label
        if value is not None:
            self.set_value(value)
        else:
            self.set_values(values)
        if type in ['list-single', 'list-multi']:
            for value, label in options.iteritems():
                self.addChild(Option(value, label))

    def set_value(self, value):
        if self['type'] == 'boolean':
            value = str(int(bool(value)))
        else:
            value = str(value)

        value_element = self.value or self.addElement('value')
        value_element.children = []
        value_element.addContent(value)

    def set_values(self, values):
        for value in values:
            value = str(value)
            self.addElement('value', content=value)

class Option(domish.Element):
    def __init__(self, value, label=None):
        domish.Element.__init__(self, (NS_X_DATA, 'option'))
        if label is not None:
            self['label'] = label
        self.addElement('value', content=value)

class Form(domish.Element):
    def __init__(self, type, form_type):
        domish.Element.__init__(self, (NS_X_DATA, 'x'),
                                attribs={'type': type})
        self.add_field(type='hidden', var='FORM_TYPE', values=[form_type])

    def add_field(self, type='text-single', var=None, label=None,
                        value=None, values=[], options={}):
        self.addChild(Field(type, var, label, value, values, options))
