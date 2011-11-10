# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for {wokkel.data_form}.
"""

from zope.interface import verify
from zope.interface.common.mapping import IIterableMapping

from twisted.trial import unittest
from twisted.words.xish import domish
from twisted.words.protocols.jabber import jid

from wokkel import data_form

NS_X_DATA = 'jabber:x:data'

class OptionTest(unittest.TestCase):
    """
    Tests for L{data_form.Option}.
    """

    def test_toElement(self):
        """
        An option is an option element with a value child with the option value.
        """
        option = data_form.Option('value')
        element = option.toElement()

        self.assertEqual('option', element.name)
        self.assertEqual(NS_X_DATA, element.uri)
        self.assertEqual(NS_X_DATA, element.value.uri)
        self.assertEqual('value', unicode(element.value))
        self.assertFalse(element.hasAttribute('label'))


    def test_toElementLabel(self):
        """
        A label is rendered as an attribute on the option element.
        """
        option = data_form.Option('value', 'label')
        element = option.toElement()

        self.assertEqual('option', element.name)
        self.assertEqual(NS_X_DATA, element.uri)
        self.assertEqual(NS_X_DATA, element.value.uri)
        self.assertEqual('value', unicode(element.value))
        self.assertEqual('label', element['label'])


    def test_fromElement(self):
        """
        An option has a child element with the option value.
        """
        element = domish.Element((NS_X_DATA, 'option'))
        element.addElement('value', content='value')
        option = data_form.Option.fromElement(element)

        self.assertEqual('value', option.value)
        self.assertIdentical(None, option.label)


    def test_fromElementLabel(self):
        """
        An option label is an attribute on the option element.
        """

        element = domish.Element((NS_X_DATA, 'option'))
        element.addElement('value', content='value')
        element['label'] = 'label'
        option = data_form.Option.fromElement(element)

        self.assertEqual('label', option.label)


    def test_fromElementNoValue(self):
        """
        An option MUST have a value.
        """
        element = domish.Element((NS_X_DATA, 'option'))
        self.assertRaises(data_form.Error,
                          data_form.Option.fromElement, element)


    def test_repr(self):
        """
        The representation of an Option is equal to how it is created.
        """
        option = data_form.Option('value', 'label')
        self.assertEqual("""Option('value', 'label')""", repr(option))



class FieldTest(unittest.TestCase):
    """
    Tests for L{data_form.Field}.
    """

    def test_basic(self):
        """
        Test basic field initialization.
        """
        field = data_form.Field(var='test')
        self.assertEqual('text-single', field.fieldType)
        self.assertEqual('test', field.var)


    def test_labelAndOptions(self):
        """
        The label should be set, even if there are options with labels as dict.
        """
        field = data_form.Field(label='test',
                                options={'test2': 'test 2', 'test3': 'test 3'})
        self.assertEqual('test', field.label)


    def test_repr(self):
        """
        The repr of a field should be equal to its initialization.
        """
        field = data_form.Field('list-single', var='test', label='label',
                               desc='desc', required=True, value='test',
                               options=[data_form.Option('test')])
        self.assertEqual("""Field(fieldType='list-single', """
                         """var='test', label='label', """
                         """desc='desc', required=True, """
                         """values=['test'], """
                         """options=[Option('test')])""",
                         repr(field))


    def test_toElement(self):
        """
        Test rendering to a DOM.
        """
        field = data_form.Field(var='test')
        element = field.toElement()

        self.assertTrue(domish.IElement.providedBy(element))
        self.assertEquals('field', element.name)
        self.assertEquals(NS_X_DATA, element.uri)
        self.assertEquals('text-single',
                          element.getAttribute('type', 'text-single'))
        self.assertEquals('test', element['var'])
        self.assertEquals([], element.children)


    def test_toElementTypeNotTextSingle(self):
        """
        Always render the field type, if different from text-single.
        """
        field = data_form.Field('hidden', var='test')
        element = field.toElement()

        self.assertEquals('hidden', element.getAttribute('type'))


    def test_toElementSingleValue(self):
        """
        A single value should yield only one value element.
        """
        field = data_form.Field('list-multi', var='test', value='test')
        element = field.toElement()

        children = list(element.elements())
        self.assertEqual(1, len(children))


    def test_toElementMultipleValues(self):
        """
        A field with no type and multiple values should render all values.
        """
        field = data_form.Field('list-multi', var='test',
                                values=['test', 'test2'])
        element = field.toElement()

        children = list(element.elements())
        self.assertEqual(2, len(children))


    def test_toElementAsForm(self):
        """
        Always render the field type, if asForm is True.
        """
        field = data_form.Field(var='test')
        element = field.toElement(True)

        self.assertEquals('text-single', element.getAttribute('type'))


    def test_toElementOptions(self):
        """
        Test rendering to a DOM with options.
        """
        field = data_form.Field('list-single', var='test')
        field.options = [data_form.Option(u'option1'),
                         data_form.Option(u'option2')]
        element = field.toElement(True)

        self.assertEqual(2, len(element.children))


    def test_toElementLabel(self):
        """
        Test rendering to a DOM with a label.
        """
        field = data_form.Field(var='test', label=u'my label')
        element = field.toElement(True)

        self.assertEqual(u'my label', element.getAttribute('label'))


    def test_toElementDescription(self):
        """
        Test rendering to a DOM with options.
        """
        field = data_form.Field(var='test', desc=u'My desc')
        element = field.toElement(True)

        self.assertEqual(1, len(element.children))
        child = element.children[0]
        self.assertEqual('desc', child.name)
        self.assertEqual(NS_X_DATA, child.uri)
        self.assertEqual(u'My desc', unicode(child))


    def test_toElementRequired(self):
        """
        Test rendering to a DOM with options.
        """
        field = data_form.Field(var='test', required=True)
        element = field.toElement(True)

        self.assertEqual(1, len(element.children))
        child = element.children[0]
        self.assertEqual('required', child.name)
        self.assertEqual(NS_X_DATA, child.uri)


    def test_toElementJID(self):
        """
        A JID value should render to text.
        """
        field = data_form.Field(fieldType='jid-single', var='test',
                                value=jid.JID(u'test@example.org'))
        element = field.toElement()
        self.assertEqual(u'test@example.org', unicode(element.value))


    def test_toElementJIDTextSingle(self):
        """
        A JID value should render to text if field type is text-single.
        """
        field = data_form.Field(fieldType='text-single', var='test',
                                value=jid.JID(u'test@example.org'))
        element = field.toElement()
        self.assertEqual(u'test@example.org', unicode(element.value))


    def test_toElementBoolean(self):
        """
        A boolean value should render to text.
        """
        field = data_form.Field(fieldType='boolean', var='test',
                                value=True)
        element = field.toElement()
        self.assertEqual(u'true', unicode(element.value))


    def test_toElementBooleanTextSingle(self):
        """
        A boolean value should render to text if the field type is text-single.
        """
        field = data_form.Field(var='test', value=True)
        element = field.toElement()
        self.assertEqual(u'true', unicode(element.value))


    def test_toElementNoType(self):
        """
        A field with no type should not have a type attribute.
        """
        field = data_form.Field(None, var='test', value='test')
        element = field.toElement()
        self.assertFalse(element.hasAttribute('type'))


    def test_toElementNoTypeMultipleValues(self):
        """
        A field with no type and multiple values should render all values.
        """
        field = data_form.Field(None, var='test', values=['test', 'test2'])
        element = field.toElement()

        self.assertFalse(element.hasAttribute('type'))
        children = list(element.elements())
        self.assertEqual(2, len(children))


    def test_typeCheckNoFieldName(self):
        """
        A field not of type fixed must have a var.
        """
        field = data_form.Field(fieldType='list-single')
        self.assertRaises(data_form.FieldNameRequiredError, field.typeCheck)


    def test_typeCheckTooManyValues(self):
        """
        Expect an exception if too many values are set, depending on type.
        """
        field = data_form.Field(fieldType='list-single', var='test',
                                values=[u'value1', u'value2'])
        self.assertRaises(data_form.TooManyValuesError, field.typeCheck)


    def test_typeCheckBooleanFalse(self):
        """
        Test possible False values for a boolean field.
        """
        field = data_form.Field(fieldType='boolean', var='test')

        for value in (False, 0, '0', 'false', 'False', []):
            field.value = value
            field.typeCheck()
            self.assertIsInstance(field.value, bool)
            self.assertFalse(field.value)


    def test_typeCheckBooleanTrue(self):
        """
        Test possible True values for a boolean field.
        """
        field = data_form.Field(fieldType='boolean', var='test')

        for value in (True, 1, '1', 'true', 'True', ['test']):
            field.value = value
            field.typeCheck()
            self.assertIsInstance(field.value, bool)
            self.assertTrue(field.value)


    def test_typeCheckBooleanBad(self):
        """
        A bad value for a boolean field should raise a ValueError
        """
        field = data_form.Field(fieldType='boolean', var='test')
        field.value = 'test'
        self.assertRaises(ValueError, field.typeCheck)


    def test_typeCheckJID(self):
        """
        The value of jid field should be a JID or coercable to one.
        """
        field = data_form.Field(fieldType='jid-single', var='test',
                                value=jid.JID('test@example.org'))
        field.typeCheck()


    def test_typeCheckJIDString(self):
        """
        The string value of jid field should be coercable into a JID.
        """
        field = data_form.Field(fieldType='jid-single', var='test',
                                value='test@example.org')
        field.typeCheck()
        self.assertEquals(jid.JID(u'test@example.org'), field.value)


    def test_typeCheckJIDBad(self):
        """
        An invalid JID string should raise an exception.
        """
        field = data_form.Field(fieldType='jid-single', var='test',
                                value='test@@example.org')
        self.assertRaises(jid.InvalidFormat, field.typeCheck)


    def test_fromElementType(self):
        element = domish.Element((NS_X_DATA, 'field'))
        element['type'] = 'fixed'
        field = data_form.Field.fromElement(element)
        self.assertEquals('fixed', field.fieldType)


    def test_fromElementNoType(self):
        element = domish.Element((NS_X_DATA, 'field'))
        field = data_form.Field.fromElement(element)
        self.assertEquals(None, field.fieldType)


    def test_fromElementValueTextSingle(self):
        """
        Parsed text-single field values should be of type C{unicode}.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element['type'] = 'text-single'
        element.addElement('value', content=u'text')
        field = data_form.Field.fromElement(element)
        self.assertEquals('text', field.value)


    def test_fromElementValueJID(self):
        """
        Parsed jid-single field values should be of type C{unicode}.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element['type'] = 'jid-single'
        element.addElement('value', content=u'user@example.org')
        field = data_form.Field.fromElement(element)
        self.assertEquals(u'user@example.org', field.value)


    def test_fromElementValueJIDMalformed(self):
        """
        Parsed jid-single field values should be of type C{unicode}.

        No validation should be done at this point, so invalid JIDs should
        also be passed as-is.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element['type'] = 'jid-single'
        element.addElement('value', content=u'@@')
        field = data_form.Field.fromElement(element)
        self.assertEquals(u'@@', field.value)


    def test_fromElementValueBoolean(self):
        """
        Parsed boolean field values should be of type C{unicode}.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element['type'] = 'boolean'
        element.addElement('value', content=u'false')
        field = data_form.Field.fromElement(element)
        self.assertEquals(u'false', field.value)


    def test_fromElementDesc(self):
        """
        Field descriptions are in a desc child element.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element.addElement('desc', content=u'My description')
        field = data_form.Field.fromElement(element)
        self.assertEqual(u'My description', field.desc)


    def test_fromElementOption(self):
        """
        Field descriptions are in a desc child element.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element.addElement('option').addElement('value', content=u'option1')
        element.addElement('option').addElement('value', content=u'option2')
        field = data_form.Field.fromElement(element)
        self.assertEqual(2, len(field.options))


    def test_fromElementRequired(self):
        """
        Required fields have a required child element.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element.addElement('required')
        field = data_form.Field.fromElement(element)
        self.assertTrue(field.required)


    def test_fromElementChildOtherNamespace(self):
        """
        Child elements from another namespace are ignored.
        """
        element = domish.Element((NS_X_DATA, 'field'))
        element['var'] = 'test'
        element.addElement(('myns', 'value'))
        field = data_form.Field.fromElement(element)

        self.assertIdentical(None, field.value)


    def test_fromDict(self):
        """
        A named field with a value can be created by providing a dictionary.
        """
        fieldDict = {'var': 'test', 'value': 'text'}
        field = data_form.Field.fromDict(fieldDict)
        self.assertEqual('test', field.var)
        self.assertEqual('text', field.value)


    def test_fromDictFieldType(self):
        """
        The field type is set using the key 'type'.
        """
        fieldDict = {'type': 'boolean'}
        field = data_form.Field.fromDict(fieldDict)
        self.assertEqual('boolean', field.fieldType)


    def test_fromDictOptions(self):
        """
        The field options are set using the key 'options'.

        The options are represented as a dictionary keyed by option,
        with the optional label as value.
        """
        fieldDict = {'options': {'value1': 'label1',
                                 'value2': 'label2'}}
        field = data_form.Field.fromDict(fieldDict)
        self.assertEqual(2, len(field.options))
        options = {}
        for option in field.options:
            options[option.value] = option.label

        self.assertEqual(options, fieldDict['options'])


class FormTest(unittest.TestCase):
    """
    Tests for L{data_form.Form}.
    """

    def test_formType(self):
        """
        A form has a type.
        """

        form = data_form.Form('result')
        self.assertEqual('result', form.formType)


    def test_toElement(self):
        """
        The toElement method returns a form's DOM representation.
        """
        form = data_form.Form('result')
        element = form.toElement()

        self.assertTrue(domish.IElement.providedBy(element))
        self.assertEquals('x', element.name)
        self.assertEquals(NS_X_DATA, element.uri)
        self.assertEquals('result', element['type'])
        self.assertEquals([], element.children)


    def test_toElementTitle(self):
        """
        A title is rendered as a child element with the title as CDATA.
        """
        form = data_form.Form('form', title='Bot configuration')
        element = form.toElement()

        elements = list(element.elements())
        self.assertEqual(1, len(elements))
        title = elements[0]
        self.assertEqual('title', title.name)
        self.assertEqual(NS_X_DATA, title.uri)
        self.assertEqual('Bot configuration', unicode(title))


    def test_toElementInstructions(self):
        """
        Instructions are rendered as child elements with CDATA.
        """
        form = data_form.Form('form', instructions=['Fill out this form!'])
        element = form.toElement()

        elements = list(element.elements())
        self.assertEqual(1, len(elements))
        instructions = elements[0]
        self.assertEqual('instructions', instructions.name)
        self.assertEqual(NS_X_DATA, instructions.uri)
        self.assertEqual('Fill out this form!', unicode(instructions))


    def test_toElementInstructionsMultiple(self):
        """
        Instructions render as one element per instruction, in order.
        """
        form = data_form.Form('form', instructions=['Fill out this form!',
                                                    'no really'])
        element = form.toElement()

        elements = list(element.elements())
        self.assertEqual(2, len(elements))
        instructions1 = elements[0]
        instructions2 = elements[1]
        self.assertEqual('instructions', instructions1.name)
        self.assertEqual(NS_X_DATA, instructions1.uri)
        self.assertEqual('Fill out this form!', unicode(instructions1))
        self.assertEqual('instructions', instructions2.name)
        self.assertEqual(NS_X_DATA, instructions2.uri)
        self.assertEqual('no really', unicode(instructions2))


    def test_toElementFormType(self):
        """
        The form type is rendered as a hidden field with name FORM_TYPE.
        """
        form = data_form.Form('form', formNamespace='jabber:bot')
        element = form.toElement()

        elements = list(element.elements())
        self.assertEqual(1, len(elements))
        formTypeField = elements[0]
        self.assertEqual('field', formTypeField.name)
        self.assertEqual(NS_X_DATA, formTypeField.uri)
        self.assertEqual('FORM_TYPE', formTypeField['var'])
        self.assertEqual('hidden', formTypeField['type'])
        self.assertEqual('jabber:bot', unicode(formTypeField.value))


    def test_toElementFields(self):
        """
        Fields are rendered as child elements, in order.
        """
        fields = [data_form.Field('fixed', value='Section 1'),
                  data_form.Field('text-single',
                                  var='botname',
                                  label='The name of your bot'),
                  data_form.Field('text-multi',
                                  var='description',
                                  label='Helpful description of your bot'),
                  data_form.Field('boolean',
                                  var='public',
                                  label='Public bot?',
                                  required=True)
                 ]
        form = data_form.Form('form', fields=fields)
        element = form.toElement()

        elements = list(element.elements())
        self.assertEqual(4, len(elements))
        for field in elements:
            self.assertEqual('field', field.name)
            self.assertEqual(NS_X_DATA, field.uri)

        # Check order
        self.assertEqual('fixed', elements[0]['type'])
        self.assertEqual('botname', elements[1]['var'])
        self.assertEqual('description', elements[2]['var'])
        self.assertEqual('public', elements[3]['var'])


    def test_fromElement(self):
        """
        C{fromElement} creates a L{data_form.Form} from a DOM representation.
        """
        element = domish.Element((NS_X_DATA, 'x'))
        element['type'] = 'result'
        form = data_form.Form.fromElement(element)

        self.assertEquals('result', form.formType)
        self.assertEquals(None, form.title)
        self.assertEquals([], form.instructions)
        self.assertEquals({}, form.fields)


    def test_fromElementInvalidElementName(self):
        """
        Bail if the passed element does not have the correct name.
        """
        element = domish.Element((NS_X_DATA, 'form'))
        self.assertRaises(Exception, data_form.Form.fromElement, element)


    def test_fromElementInvalidElementURI(self):
        """
        Bail if the passed element does not have the correct namespace.
        """
        element = domish.Element(('myns', 'x'))
        self.assertRaises(Exception, data_form.Form.fromElement, element)


    def test_fromElementTitle(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('title', content='My title')
        form = data_form.Form.fromElement(element)

        self.assertEquals('My title', form.title)


    def test_fromElementInstructions(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('instructions', content='instruction')
        form = data_form.Form.fromElement(element)

        self.assertEquals(['instruction'], form.instructions)


    def test_fromElementInstructions2(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('instructions', content='instruction 1')
        element.addElement('instructions', content='instruction 2')
        form = data_form.Form.fromElement(element)

        self.assertEquals(['instruction 1', 'instruction 2'], form.instructions)


    def test_fromElementOneField(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('field')
        form = data_form.Form.fromElement(element)

        self.assertEquals(1, len(form.fieldList))
        self.assertNotIn('field', form.fields)


    def test_fromElementTwoFields(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('field')['var'] = 'field1'
        element.addElement('field')['var'] = 'field2'
        form = data_form.Form.fromElement(element)

        self.assertEquals(2, len(form.fieldList))
        self.assertIn('field1', form.fields)
        self.assertEquals('field1', form.fieldList[0].var)
        self.assertIn('field2', form.fields)
        self.assertEquals('field2', form.fieldList[1].var)


    def test_fromElementFormType(self):
        """
        The form type is a hidden field named FORM_TYPE.
        """
        element = domish.Element((NS_X_DATA, 'x'))
        field = element.addElement('field')
        field['var'] = 'FORM_TYPE'
        field['type'] = 'hidden'
        field.addElement('value', content='myns')
        form = data_form.Form.fromElement(element)

        self.assertNotIn('FORM_TYPE', form.fields)
        self.assertEqual('myns', form.formNamespace)

    def test_fromElementFormTypeNotHidden(self):
        """
        A non-hidden field named FORM_TYPE does not set the form type.
        """
        element = domish.Element((NS_X_DATA, 'x'))
        field = element.addElement('field')
        field['var'] = 'FORM_TYPE'
        field.addElement('value', content='myns')
        form = data_form.Form.fromElement(element)

        self.assertIn('FORM_TYPE', form.fields)
        self.assertIdentical(None, form.formNamespace)


    def test_fromElementChildOtherNamespace(self):
        """
        Child elements from another namespace are ignored.
        """
        element = domish.Element((NS_X_DATA, 'x'))
        element['type'] = 'result'
        field = element.addElement(('myns', 'field'))
        field['var'] = 'test'
        form = data_form.Form.fromElement(element)

        self.assertEqual(0, len(form.fields))


    def test_repr(self):
        """
        The repr of a form should be equal to its initialization.
        """
        form = data_form.Form('form', title='title', instructions=['instr'],
                                      formNamespace='myns',
                                      fields=[data_form.Field('fixed',
                                                              value='test')])
        self.assertEqual("""Form(formType='form', title='title', """
                         """instructions=['instr'], formNamespace='myns', """
                         """fields=[Field(fieldType='fixed', """
                         """values=['test'])])""",
                         repr(form))


    def test_addField(self):
        """
        A field should occur in fieldList.
        """
        form = data_form.Form('result')
        field = data_form.Field('fixed', value='Section 1')
        form.addField(field)
        self.assertEqual([field], form.fieldList)


    def test_addFieldTwice(self):
        """
        Fields occur in fieldList in the order they were added.
        """
        form = data_form.Form('result')
        field1 = data_form.Field('fixed', value='Section 1')
        field2 = data_form.Field('fixed', value='Section 2')
        form.addField(field1)
        form.addField(field2)
        self.assertEqual([field1, field2], form.fieldList)


    def test_addFieldNotNamed(self):
        """
        A non-named field should not occur in fields.
        """
        form = data_form.Form('result')
        field = data_form.Field('fixed', value='Section 1')
        form.addField(field)
        self.assertEqual({}, form.fields)


    def test_addFieldNamed(self):
        """
        A named field should occur in fields.
        """
        form = data_form.Form('result')
        field = data_form.Field(var='test')
        form.addField(field)
        self.assertEqual({'test': field}, form.fields)


    def test_addFieldTwiceNamed(self):
        """
        A second named field should occur in fields.
        """
        form = data_form.Form('result')
        field1 = data_form.Field(var='test')
        field2 = data_form.Field(var='test2')
        form.addField(field2)
        form.addField(field1)
        self.assertEqual({'test': field1, 'test2': field2}, form.fields)


    def test_addFieldSameName(self):
        """
        A named field cannot occur twice.
        """
        form = data_form.Form('result')
        field1 = data_form.Field(var='test', value='value')
        field2 = data_form.Field(var='test', value='value2')
        form.addField(field1)
        self.assertRaises(data_form.Error, form.addField, field2)


    def test_removeField(self):
        """
        A removed field should not occur in fieldList.
        """
        form = data_form.Form('result')
        field = data_form.Field('fixed', value='Section 1')
        form.addField(field)
        form.removeField(field)
        self.assertNotIn(field, form.fieldList)


    def test_removeFieldNamed(self):
        """
        A removed named field should not occur in fields.
        """
        form = data_form.Form('result')
        field = data_form.Field(var='test', value='test1')
        form.addField(field)
        form.removeField(field)
        self.assertNotIn('test', form.fields)


    def test_makeField(self):
        """
        Fields can be created from a dict of values and a dict of field defs.
        """
        fieldDefs = {
                "pubsub#persist_items":
                    {"type": "boolean",
                     "label": "Persist items to storage"},
                "pubsub#deliver_payloads":
                    {"type": "boolean",
                     "label": "Deliver payloads with event notifications"},
                "pubsub#creator":
                    {"type": "jid-single",
                     "label": "The JID of the node creator"},
                "pubsub#description":
                    {"type": "text-single",
                     "label": "A description of the node"},
                "pubsub#owner":
                    {"type": "jid-single",
                     "label": "Owner of the node"},
                }
        values = {'pubsub#deliver_payloads': '0',
                  'pubsub#persist_items': True,
                  'pubsub#description': 'a great node',
                  'pubsub#owner': jid.JID('user@example.org'),
                  'x-myfield': ['a', 'b']}

        form = data_form.Form('submit')
        form.makeFields(values, fieldDefs)

        # Check that the expected fields have been created
        self.assertIn('pubsub#deliver_payloads', form.fields)
        self.assertIn('pubsub#persist_items', form.fields)
        self.assertIn('pubsub#description', form.fields)
        self.assertIn('pubsub#owner', form.fields)

        # This field is not created because there is no value for it.
        self.assertNotIn('pubsub#creator', form.fields)

        # This field is not created because it does not appear in fieldDefs
        # and filterUnknown defaults to True
        self.assertNotIn('x-myfield', form.fields)

        # Check properties the created fields
        self.assertEqual('boolean',
                         form.fields['pubsub#deliver_payloads'].fieldType)
        self.assertEqual('0',
                         form.fields['pubsub#deliver_payloads'].value)
        self.assertEqual('Deliver payloads with event notifications',
                         form.fields['pubsub#deliver_payloads'].label)
        self.assertEqual(True,
                         form.fields['pubsub#persist_items'].value)


    def test_makeFieldNotFilterUnknown(self):
        """
        Fields can be created from a dict of values and a dict of field defs.
        """
        fieldDefs = {
                "pubsub#persist_items":
                    {"type": "boolean",
                     "label": "Persist items to storage"},
                }
        values = {'x-myfield': ['a', 'b']}

        form = data_form.Form('submit')
        form.makeFields(values, fieldDefs, filterUnknown=False)

        field = form.fields['x-myfield']
        self.assertEqual(None, field.fieldType)
        self.assertEqual(values, form.getValues())


    def test_makeFieldsUnknownTypeJID(self):
        """
        Without type, a single JID value sets field type jid-single.
        """
        values = {'pubsub#creator': jid.JID('user@example.org')}
        form = data_form.Form('result')
        form.makeFields(values)

        field = form.fields['pubsub#creator']
        self.assertEqual(None, field.fieldType)
        self.assertEqual(values, form.getValues())


    def test_makeFieldsUnknownTypeJIDMulti(self):
        """
        Without type, multiple JID values sets field type jid-multi.
        """
        values = {'pubsub#contact': [jid.JID('user@example.org'),
                                     jid.JID('other@example.org')]}
        form = data_form.Form('result')
        form.makeFields(values)

        field = form.fields['pubsub#contact']
        self.assertEqual(None, field.fieldType)
        self.assertEqual(values, form.getValues())


    def test_makeFieldsUnknownTypeBoolean(self):
        """
        Without type, a boolean value sets field type boolean.
        """
        values = {'pubsub#persist_items': True}
        form = data_form.Form('result')
        form.makeFields(values)

        field = form.fields['pubsub#persist_items']
        self.assertEqual(None, field.fieldType)
        self.assertEqual(values, form.getValues())


    def test_makeFieldsUnknownTypeListMulti(self):
        """
        Without type, multiple values sets field type list-multi.
        """
        values = {'pubsub#show-values': ['chat', 'online', 'away']}
        form = data_form.Form('result')
        form.makeFields(values)

        field = form.fields['pubsub#show-values']
        self.assertEqual(None, field.fieldType)
        self.assertEqual(values, form.getValues())


    def test_interface(self):
        """
        L{Form}s act as a read-only dictionary.
        """
        form = data_form.Form('submit')
        verify.verifyObject(IIterableMapping, form)


    def test_getitem(self):
        """
        Using Form as a mapping will yield the value of fields keyed by name.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True),
                  data_form.Field('list-multi', var='features',
                                                values=['news', 'search'])]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual('The Jabber Bot', form['botname'])
        self.assertTrue(form['public'])
        self.assertEqual(['news', 'search'], form['features'])


    def test_getitemOneValueTypeMulti(self):
        """
        A single value for a multi-value field type is returned in a list.
        """
        fields = [data_form.Field('list-multi', var='features',
                                                values=['news'])]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual(['news'], form['features'])


    def test_getitemMultipleValuesNoType(self):
        """
        Multiple values for a field without type are returned in a list.
        """
        fields = [data_form.Field(None, var='features',
                                        values=['news', 'search'])]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual(['news', 'search'], form['features'])


    def test_getitemMultipleValuesTypeSingle(self):
        """
        Multiple values for a single-value field type returns the first value.
        """
        fields = [data_form.Field('text-single', var='features',
                                        values=['news', 'search'])]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual('news', form['features'])


    def test_get(self):
        """
        Getting the value of a known field succeeds.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot')]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual('The Jabber Bot', form.get('botname'))


    def test_getUnknownNone(self):
        """
        Getting the value of a unknown field returns None.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot')]
        form = data_form.Form('submit', fields=fields)
        self.assertIdentical(None, form.get('features'))


    def test_getUnknownDefault(self):
        """
        Getting the value of a unknown field returns specified default.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot')]
        form = data_form.Form('submit', fields=fields)
        self.assertTrue(form.get('public', True))


    def test_contains(self):
        """
        A form contains a known field.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot')]
        form = data_form.Form('submit', fields=fields)
        self.assertIn('botname', form)


    def test_containsNot(self):
        """
        A form does not contains an unknown field.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot')]
        form = data_form.Form('submit', fields=fields)
        self.assertNotIn('features', form)


    def test_iterkeys(self):
        """
        Iterating over the keys of a form yields all field names.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True),
                  data_form.Field('list-multi', var='features',
                                                values=['news', 'search'])]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual(set(['botname', 'public', 'features']),
                         set(form.iterkeys()))


    def test_itervalues(self):
        """
        Iterating over the values of a form yields all field values.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True)]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual(set(['The Jabber Bot', True]),
                         set(form.itervalues()))


    def test_iteritems(self):
        """
        Iterating over the values of a form yields all item tuples.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True)]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual(set([('botname', 'The Jabber Bot'),
                              ('public', True)]),
                         set(form.iteritems()))


    def test_keys(self):
        """
        Getting the keys of a form yields a list of field names.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True),
                  data_form.Field('list-multi', var='features',
                                                values=['news', 'search'])]
        form = data_form.Form('submit', fields=fields)
        keys = form.keys()
        self.assertIsInstance(keys, list)
        self.assertEqual(set(['botname', 'public', 'features']),
                         set(keys))


    def test_values(self):
        """
        Getting the values of a form yields a list of field values.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True)]
        form = data_form.Form('submit', fields=fields)
        values = form.values()
        self.assertIsInstance(values, list)
        self.assertEqual(set(['The Jabber Bot', True]), set(values))


    def test_items(self):
        """
        Iterating over the values of a form yields a list of all item tuples.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True)]
        form = data_form.Form('submit', fields=fields)
        items = form.items()
        self.assertIsInstance(items, list)
        self.assertEqual(set([('botname', 'The Jabber Bot'),
                              ('public', True)]),
                         set(items))


    def test_getValues(self):
        """
        L{Form.getValues} returns a dict of all field values.
        """
        fields = [data_form.Field(var='botname', value='The Jabber Bot'),
                  data_form.Field('boolean', var='public', value=True),
                  data_form.Field('list-multi', var='features',
                                                values=['news', 'search'])]
        form = data_form.Form('submit', fields=fields)
        self.assertEqual({'botname': 'The Jabber Bot',
                          'public': True,
                          'features': ['news', 'search']},
                         form.getValues())


    def test_typeCheckKnownFieldChecked(self):
        """
        Known fields are type checked.
        """
        checked = []
        fieldDefs = {"pubsub#description":
                        {"type": "text-single",
                         "label": "A description of the node"}}
        form = data_form.Form('submit')
        form.addField(data_form.Field(var='pubsub#description',
                                      value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)
        form.typeCheck(fieldDefs)

        self.assertEqual([None], checked)


    def test_typeCheckKnownFieldNoType(self):
        """
        Known fields without a type get the type of the field definition.
        """
        checked = []
        fieldDefs = {"pubsub#description":
                        {"type": "text-single",
                         "label": "A description of the node"}}
        form = data_form.Form('submit')
        form.addField(data_form.Field(None, var='pubsub#description',
                                            value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)
        form.typeCheck(fieldDefs)

        self.assertEqual('text-single', field.fieldType)
        self.assertEqual([None], checked)


    def test_typeCheckWrongFieldType(self):
        """
        A field should have the same type as the field definition.
        """
        checked = []
        fieldDefs = {"pubsub#description":
                        {"type": "text-single",
                         "label": "A description of the node"}}
        form = data_form.Form('submit')
        form.addField(data_form.Field('list-single', var='pubsub#description',
                                                     value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)

        self.assertRaises(TypeError, form.typeCheck, fieldDefs)
        self.assertEqual([], checked)


    def test_typeCheckDefaultTextSingle(self):
        """
        If a field definition has no type, use text-single.
        """
        checked = []
        fieldDefs = {"pubsub#description":
                        {"label": "A description of the node"}}
        form = data_form.Form('submit')
        form.addField(data_form.Field('text-single', var='pubsub#description',
                                                     value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)
        form.typeCheck(fieldDefs)

        self.assertEqual([None], checked)


    def test_typeCheckUnknown(self):
        """
        Unknown fields are checked, not removed if filterUnknown False.
        """
        checked = []
        fieldDefs = {}
        form = data_form.Form('submit')
        form.addField(data_form.Field('list-single', var='pubsub#description',
                                                     value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)
        form.typeCheck(fieldDefs, filterUnknown=False)

        self.assertIn('pubsub#description', form.fields)
        self.assertEqual([None], checked)


    def test_typeCheckUnknownNoType(self):
        """
        Unknown fields without type are not checked.
        """
        checked = []
        fieldDefs = {}
        form = data_form.Form('submit')
        form.addField(data_form.Field(None, var='pubsub#description',
                                            value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)
        form.typeCheck(fieldDefs, filterUnknown=False)

        self.assertIn('pubsub#description', form.fields)
        self.assertEqual([], checked)


    def test_typeCheckUnknownRemoved(self):
        """
        Unknown fields are not checked, and removed if filterUnknown True.
        """
        checked = []
        fieldDefs = {}
        form = data_form.Form('submit')
        form.addField(data_form.Field('list-single', var='pubsub#description',
                                                     value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)
        form.typeCheck(fieldDefs, filterUnknown=True)

        self.assertNotIn('pubsub#description', form.fields)
        self.assertEqual([], checked)



class FindFormTest(unittest.TestCase):
    """
    Tests for L{data_form.findForm}.
    """

    def test_findForm(self):
        element = domish.Element((None, 'test'))
        theForm = data_form.Form('submit', formNamespace='myns')
        element.addChild(theForm.toElement())
        form = data_form.findForm(element, 'myns')
        self.assertEqual('myns', form.formNamespace)


    def test_noFormType(self):
        element = domish.Element((None, 'test'))
        otherForm = data_form.Form('submit')
        element.addChild(otherForm.toElement())
        form = data_form.findForm(element, 'myns')
        self.assertIdentical(None, form)


    def test_noFormTypeCancel(self):
        """
        Cancelled forms don't have a FORM_TYPE field, the first is returned.
        """
        element = domish.Element((None, 'test'))
        cancelledForm = data_form.Form('cancel')
        element.addChild(cancelledForm.toElement())
        form = data_form.findForm(element, 'myns')
        self.assertEqual('cancel', form.formType)


    def test_otherFormType(self):
        """
        Forms with other FORM_TYPEs are ignored.
        """
        element = domish.Element((None, 'test'))
        otherForm = data_form.Form('submit', formNamespace='otherns')
        element.addChild(otherForm.toElement())
        form = data_form.findForm(element, 'myns')
        self.assertIdentical(None, form)


    def test_otherFormTypeCancel(self):
        """
        Cancelled forms with another FORM_TYPE are ignored.
        """
        element = domish.Element((None, 'test'))
        cancelledForm = data_form.Form('cancel', formNamespace='otherns')
        element.addChild(cancelledForm.toElement())
        form = data_form.findForm(element, 'myns')
        self.assertIdentical(None, form)


    def test_noElement(self):
        """
        When None is passed as element, None is returned.
        """
        element = None
        form = data_form.findForm(element, 'myns')
        self.assertIdentical(None, form)


    def test_noForm(self):
        """
        When no child element is a form, None is returned.
        """
        element = domish.Element((None, 'test'))
        form = data_form.findForm(element, 'myns')
        self.assertIdentical(None, form)
    def test_typeCheckNoFieldDefs(self):
        """
        If there are no field defs, an empty dictionary is assumed.
        """
        checked = []
        form = data_form.Form('submit')
        form.addField(data_form.Field('list-single', var='pubsub#description',
                                                     value='a node'))
        field = form.fields['pubsub#description']
        field.typeCheck = lambda : checked.append(None)
        form.typeCheck()

        self.assertIn('pubsub#description', form.fields)
        self.assertEqual([None], checked)
