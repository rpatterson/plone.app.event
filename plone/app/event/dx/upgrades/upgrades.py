# -*- coding: utf-8 -*-
from Products.CMFCore.utils import getToolByName
from plone.app.event.dx.interfaces import IDXEvent
from plone.app.event.dx.behaviors import IEventAttendees
from plone.app.event.dx.behaviors import IEventContact
from plone.app.event.dx.behaviors import IEventLocation
from zope.annotation.interfaces import IAnnotatable
from zope.annotation.interfaces import IAnnotations

from zope.component.hooks import getSite

import logging
log = logging.getLogger(__name__)

BEHAVIOR_LIST = [
    IEventAttendees,
    IEventContact,
    IEventLocation,
]


def upgrade_attribute_storage(context):
    portal = getSite()
    catalog = getToolByName(portal, 'portal_catalog')
    query = {}
    query['object_provides'] = IDXEvent.__identifier__
    results = catalog(**query)
    log.info('There are {0} in total, stating migration...'.format(
        len(results)))
    for result in results:
        try:
            event = result.getObject()
        except:
            log.warning(
                'Not possible to fetch event object from catalog result for '
                'item: {0}.'.format(result.getPath()))
            continue
        if not IAnnotatable.providedBy(event):
            log.warning(
                'The event at {0} does provide annotation capabilities, '
                'skipping.'.format(event.absolute_url()))
            continue
        annotations = IAnnotations(event)
        for behavior in BEHAVIOR_LIST:
            for name in behavior.names():
                fullname = '{0}.{1}'.format(behavior.__identifier__, name)
                oldvalue = annotations.get(fullname, None)
                # Only write the old value if there is no new value yet
                if not getattr(event, name, None):
                    setattr(event, name, oldvalue)
        log.debug('Handled event at {0}'.format(event.absolute_url()))