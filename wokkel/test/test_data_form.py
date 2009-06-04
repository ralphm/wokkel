# Copyright (c) 2003-2009 Ralph Meijer
# See LICENSE for details.

"""
Tests for {wokkel.data_form}.
"""

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
        option = data_form.Option('value', 'label')
        element = option.toElement()
        self.assertEquals('option', element.name)
        self.assertEquals(NS_X_DATA, element.uri)
        self.assertEquals('label', element['label'])
        self.assertEquals('value', element.value.name)
        self.assertEquals(NS_X_DATA, element.value.uri)
        self.assertEquals('value', unicode(element.value))



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


    def test_toElementTypeNotListSingle(self):
        """
        Always render the field type, if different from list-single.
        """
        field = data_form.Field('hidden', var='test')
        element = field.toElement()

        self.assertEquals('hidden', element.getAttribute('type'))


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
        field = data_form.Field(fieldType='jid-single', var='test',
                                value=jid.JID(u'test@example.org'))
        element = field.toElement()
        self.assertEqual(u'test@example.org', unicode(element.value))


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
