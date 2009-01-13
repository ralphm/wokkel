# -*- test-case-name: wokkel.test.test_data_form -*-
#
# Copyright (c) 2003-2009 Ralph Meijer
# See LICENSE for details.

"""
Data Forms.

Support for Data Forms as described in
U{XEP-0004<http://www.xmpp.org/extensions/xep-0004.html>}, along with support
for Field Standardization for Data Forms as described in
U{XEP-0068<http://www.xmpp.org/extensions/xep-0068.html>}.
"""

from twisted.words.protocols.jabber.jid import JID
from twisted.words.xish import domish

NS_X_DATA = 'jabber:x:data'



class Error(Exception):
    """
    Data Forms error.
    """



class FieldNameRequiredError(Error):
    """
    A field name is required for this field type.
    """



class TooManyValuesError(Error):
    """
    This field is single-value.
    """



class Option(object):
    """
    Data Forms field option.

    @ivar value: Value of this option.
    @type value: C{unicode}
    @ivar label: Optional label for this option.
    @type label: C{unicode} or C{NoneType}.
    """

    def __init__(self, value, label=None):
        self.value = value
        self.label = label


    def __repr__(self):
        r = ["Option(", repr(self.value)]
        if self.label:
            r.append(", ")
            r.append(repr(self.label))
        r.append(")")
        return u"".join(r)


    def toElement(self):
        """
        Return the DOM representation of this option.

        @rtype: L{domish.Element}.
        """
        option = domish.Element((NS_X_DATA, 'option'))
        option.addElement('value', content=self.value)
        if self.label:
            option['label'] = self.label
        return option

    @staticmethod
    def fromElement(element):
        valueElements = list(domish.generateElementsQNamed(element.children,
                                                           'value', NS_X_DATA))
        if not valueElements:
            raise Error("Option has no value")

        label = element.getAttribute('label')
        return Option(unicode(valueElements[0]), label)


class Field(object):
    """
    Data Forms field.

    @ivar fieldType: Type of this field. One of C{'boolean'}, C{'fixed'},
                     C{'hidden'}, C{'jid-multi'}, C{'jid-single'},
                     C{'list-multi'}, {'list-single'}, C{'text-multi'},
                     C{'text-private'}, C{'text-single'}.

                     The default is C{'text-single'}.
    @type fieldType: C{str}
    @ivar var: Field name. Optional if L{fieldType} is C{'fixed'}.
    @type var: C{str}
    @ivar label: Human readable label for this field.
    @type label: C{unicode}
    @ivar values: The values for this field, for multi-valued field
                  types, as a list of C{bool}, C{unicode} or L{JID}.
    @type values: C{list}
    @ivar options: List of possible values to choose from in a response
                   to this form as a list of L{Option}s.
    @type options: C{list}.
    @ivar desc: Human readable description for this field.
    @type desc: C{unicode}
    @ivar required: Whether the field is required to be provided in a
                    response to this form.
    @type required: C{bool}.
    """

    def __init__(self, fieldType='text-single', var=None, value=None,
                       values=None, options=None, label=None, desc=None,
                       required=False):
        """
        Initialize this field.

        See the identically named instance variables for descriptions.

        If C{value} is not C{None}, it overrides C{values}, setting the
        given value as the only value for this field.
        """

        self.fieldType = fieldType
        self.var = var
        if value is not None:
            self.value = value
        else:
            self.values = values or []

        try:
            self.options = [Option(value, label)
                            for value, label in options.iteritems()]
        except AttributeError:
            self.options = options or []

        self.label = label
        self.desc = desc
        self.required = required


    def __repr__(self):
        r = ["Field(fieldType=", repr(self.fieldType)]
        if self.var:
            r.append(", var=")
            r.append(repr(self.var))
        if self.label:
            r.append(", label=")
            r.append(repr(self.label))
        if self.desc:
            r.append(", desc=")
            r.append(repr(self.desc))
        if self.required:
            r.append(", required=")
            r.append(repr(self.required))
        if self.values:
            r.append(", values=")
            r.append(repr(self.values))
        if self.options:
            r.append(", options=")
            r.append(repr(self.options))
        r.append(")")
        return u"".join(r)


    def __value_set(self, value):
        """
        Setter of value property.

        Sets C{value} as the only element of L{values}.

        @type value: C{bool}, C{unicode} or L{JID}
        """
        self.values = [value]


    def __value_get(self):
        """
        Getter of value property.

        Returns the first element of L{values}, if present, or C{None}.
        """

        if self.values:
            return self.values[0]
        else:
            return None


    value = property(__value_get, __value_set, doc="""
            The value for this field, for single-valued field types.

            This is a special property accessing L{values}.  Writing to this
            property empties L{values} and then sets the given value as the
            only element of L{values}.  Reading from this propery returns the
            first element of L{values}.
            """)


    def typeCheck(self):
        """
        Check field properties agains the set field type.
        """
        if self.var is None and self.fieldType != 'fixed':
            raise FieldNameRequiredError()

        if self.values:
            if (self.fieldType not in ('hidden', 'jid-multi', 'list-multi',
                                 'text-multi') and
                len(self.values) > 1):
                raise TooManyValuesError()

            newValues = []
            for value in self.values:
                if self.fieldType == 'boolean':
                    if isinstance(value, (str, unicode)):
                        checkValue = value.lower()
                        if not checkValue in ('0', '1', 'false', 'true'):
                            raise ValueError("Not a boolean")
                        value = checkValue in ('1', 'true')
                    value = bool(value)
                elif self.fieldType in ('jid-single', 'jid-multi'):
                    if not hasattr(value, 'full'):
                        value = JID(value)

                newValues.append(value)

            self.values = newValues

    def toElement(self, asForm=False):
        """
        Return the DOM representation of this Field.

        @rtype: L{domish.Element}.
        """

        self.typeCheck()

        field = domish.Element((NS_X_DATA, 'field'))

        if asForm or self.fieldType != 'text-single':
            field['type'] = self.fieldType

        if self.var is not None:
            field['var'] = self.var

        for value in self.values:
            if self.fieldType == 'boolean':
                value = unicode(value).lower()
            elif self.fieldType in ('jid-single', 'jid-multi'):
                value = value.full()

            field.addElement('value', content=value)

        if asForm:
            if self.fieldType in ('list-single', 'list-multi'):
                for option in self.options:
                    field.addChild(option.toElement())

            if self.label is not None:
                field['label'] = self.label

            if self.desc is not None:
                field.addElement('desc', content=self.desc)

            if self.required:
                field.addElement('required')

        return field


    @staticmethod
    def _parse_desc(field, element):
        desc = unicode(element)
        if desc:
            field.desc = desc


    @staticmethod
    def _parse_option(field, element):
        field.options.append(Option.fromElement(element))


    @staticmethod
    def _parse_required(field, element):
        field.required = True


    @staticmethod
    def _parse_value(field, element):
        value = unicode(element)
        if field.fieldType == 'boolean':
            value = value.lower() in ('1', 'true')
        elif field.fieldType in ('jid-multi', 'jid-single'):
            value = JID(value)
        field.values.append(value)


    @staticmethod
    def fromElement(element):
        field = Field(None)

        for eAttr, fAttr in {'type': 'fieldType',
                             'var': 'var',
                             'label': 'label'}.iteritems():
            value = element.getAttribute(eAttr)
            if value:
                setattr(field, fAttr, value)


        for child in element.elements():
            if child.uri != NS_X_DATA:
                continue

            func = getattr(Field, '_parse_' + child.name, None)
            if func:
                func(field, child)

        return field


    @staticmethod
    def fromDict(dictionary):
        kwargs = dictionary.copy()

        if 'type' in dictionary:
            kwargs['fieldType'] = dictionary['type']
            del kwargs['type']

        if 'options' in dictionary:
            options = []
            for value, label in dictionary['options'].iteritems():
                options.append(Option(value, label))
            kwargs['options'] = options

        return Field(**kwargs)



class Form(object):
    """
    Data Form.

    There are two similarly named properties of forms. The L{formType} is the
    the so-called type of the form, and is set as the C{'type'} attribute
    on the form's root element.

    The Field Standardization specification in XEP-0068, defines a way to
    provide a context for the field names used in this form, by setting a
    special hidden field named C{'FORM_TYPE'}, to put the names of all
    other fields in the namespace of the value of that field. This namespace
    is recorded in the L{formNamespace} instance variable.

    @ivar formType: Type of form. One of C{'form'}, C{'submit'}, {'cancel'},
                    or {'result'}.
    @type formType: C{str}.
    @ivar formNamespace: The optional namespace of the field names for this
                         form. This goes in the special field named
                         C{'FORM_TYPE'}, if set.
    @type formNamespace: C{str}.
    @ivar fields: Dictionary of fields that have a name. Note that this is
                  meant to be used for reading, only. One should use
                  L{addField} for adding fields.
    @type fields: C{dict}
    """

    def __init__(self, formType, title=None, instructions=None,
                       formNamespace=None, fields=None):
        self.formType = formType
        self.title = title
        self.instructions = instructions or []
        self.formNamespace = formNamespace

        self.fieldList = []
        self.fields = {}

        if fields:
            for field in fields:
                self.addField(field)

    def __repr__(self):
        r = ["Form(formType=", repr(self.formType)]

        if self.title:
            r.append(", title=")
            r.append(repr(self.title))
        if self.instructions:
            r.append(", instructions=")
            r.append(repr(self.instructions))
        if self.formNamespace:
            r.append(", formNamespace=")
            r.append(repr(self.formNamespace))
        if self.fields:
            r.append(", fields=")
            r.append(repr(self.fieldList))
        r.append(")")
        return u"".join(r)


    def addField(self, field):
        """
        Add a field to this form.

        Fields are added in order, and L{fields} is a dictionary of the
        named fields, that is kept in sync only if this method is used for
        adding new fields. Multiple fields with the same name are disallowed.
        """
        if field.var is not None:
            if field.var in self.fields:
                raise Error("Duplicate field %r" % field.var)

            self.fields[field.var] = field

        self.fieldList.append(field)


    def toElement(self):
        form = domish.Element((NS_X_DATA, 'x'))
        form['type'] = self.formType

        if self.title:
            form.addElement('title', content=self.title)

        for instruction in self.instructions:
            form.addElement('instruction', content=instruction)

        if self.formNamespace is not None:
            field = Field('hidden', 'FORM_TYPE', self.formNamespace)
            form.addChild(field.toElement())

        for field in self.fieldList:
            form.addChild(field.toElement(self.formType=='form'))

        return form


    @staticmethod
    def _parse_title(form, element):
        title = unicode(element)
        if title:
            form.title = title


    @staticmethod
    def _parse_instructions(form, element):
        instructions = unicode(element)
        if instructions:
            form.instructions.append(instructions)


    @staticmethod
    def _parse_field(form, element):
        field = Field.fromElement(element)
        if (field.var == "FORM_TYPE" and
            field.fieldType == 'hidden' and
            field.value):
            form.formNamespace = field.value
        else:
            form.addField(field)

    @staticmethod
    def fromElement(element):
        if (element.uri, element.name) != ((NS_X_DATA, 'x')):
            raise Error("Element provided is not a Data Form")

        form = Form(element.getAttribute("type"))

        for child in element.elements():
            if child.uri != NS_X_DATA:
                continue

            func = getattr(Form, '_parse_' + child.name, None)
            if func:
                func(form, child)

        return form

    def getValues(self):
        values = {}

        for name, field in self.fields.iteritems():
            if len(field.values) > 1:
                value = field.values
            else:
                value = field.value

            values[name] = value

        return values
