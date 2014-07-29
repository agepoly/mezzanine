# -*- coding: utf-8 -*-

from django.shortcuts import get_object_or_404, render_to_response, redirect
from django.template import RequestContext
from django.core.context_processors import csrf
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.utils.encoding import smart_str
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseRedirect
from django.db import connections
from django.core.paginator import InvalidPage, EmptyPage, Paginator
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _


from .models import Form, FormEntry, Payement

from polybanking import PolyBanking


def start_payement(request, pk):
    """Start payement for a form"""

    api = PolyBanking(settings.POLYBANKING_SERVER, settings.POLYBANKING_ID, settings.POLYBANKING_KEY_REQUEST, settings.POLYBANKING_KEY_IPN, settings.POLYBANKING_KEY_API)

    entry = get_object_or_404(FormEntry, pk=pk)

    if not entry.form.need_payement:
        raise Http404

    payement = entry.get_payement()

    error = ''

    if not entry.form.can_start_payement:
        error = 'form_full'

    if payement.started:
        error = 'payement_started'

    if payement.is_valid:
        error = 'payement_already_ok'

    if not error:
        error, url = api.new_transaction(str(entry.form.amount * 100), payement.reference())

    if error != 'OK':
        return render_to_response('forms/error.html', {'error': error}, context_instance=RequestContext(request))
    else:
        payement.started = True
        payement.save()
        return HttpResponseRedirect(url)


@csrf_exempt
def ipn(request):

    api = PolyBanking(settings.POLYBANKING_SERVER, settings.POLYBANKING_ID, settings.POLYBANKING_KEY_REQUEST, settings.POLYBANKING_KEY_IPN, settings.POLYBANKING_KEY_API)

    ok, message, ref, status, status_ok, date = api.check_ipn(request.POST)

    if ok:

        payement = get_object_or_404(Payement, pk=ref.split('-')[-1])
        payement.is_valid = status_ok
        payement.save()

    return HttpResponse('')

