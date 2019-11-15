from __future__ import print_function
from __future__ import absolute_import

__license__ = """

Copyright (c) 2012-2014, Uwe Schmitt, all rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

Neither the name of the ETH Zurich nor the names of its contributors may be
used to endorse or promote products derived from this software without specific
prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import os.path
import re
from collections import defaultdict
from autowrap.ConversionProvider import setup_converter_registry
from autowrap.DeclResolver import (ResolvedClass, ResolvedEnum, ResolvedTypeDef, ResolvedFunction)
from autowrap.code_generators.CodeGeneratorBase import CodeGeneratorBase
import autowrap.Code as Code
import logging as logger

IS_PY3 = True
try:
	unicode = unicode
except NameError:
	# 'unicode' is undefined, must be Python 3
	str = str
	unicode = str
	bytes = bytes
	basestring = (str, bytes)
else:
	IS_PY3 = False
	# 'unicode' exists, must be Python 2
	str = str
	unicode = unicode
	bytes = str
	basestring = basestring

class CLRGenerator(CodeGeneratorBase):
	def __init__(self, resolved, instance_mapping, pyx_target_path=None, manual_code=None, extra_cimports=None,
				 allDecl={}):
		if IS_PY3:
			super().__init__(resolved, instance_mapping, pyx_target_path, manual_code,
							 extra_cimports, allDecl)
		else:
			super(CodeGeneratorBase, self).__init__(resolved, instance_mapping, pyx_target_path, manual_code,
													extra_cimports, allDecl)

	def create_code_file(self, debug=False):
		"""This creates the actual C++/CLI code which can be compiled to MSIL

		It calls create_wrapper_for_class, create_wrapper_for_enum and
		create_wrapper_for_free_function, ... etc, to create the wrapping code
		"""
		self.setup_cimport_paths()
		self.create_cimports()
		self.create_foreign_cimports()
		self.create_includes()

	def create_wrapper_for_enum(self, decl):
		raise NotImplementedError

	def create_wrapper_for_class(self, r_class):
		raise NotImplementedError

	def _create_iter_methods(self, iterators, instance_mapping, local_mapping):
		raise NotImplementedError

	def _create_overloaded_method_decl(self, py_name, dispatched_m_names, methods, use_return, use_kwargs=False):
		raise NotImplementedError

	def create_wrapper_for_method(self, cdcl, py_name, methods):
		raise NotImplementedError

	def _create_fun_decl_and_input_conversion(self, code, py_name, method, is_free_fun=False):
		raise NotImplementedError

	def _create_wrapper_for_attribute(self, attribute):
		raise NotImplementedError

	def create_wrapper_for_nonoverloaded_method(self, cdcl, py_name, method):
		raise NotImplementedError

	def create_wrapper_for_free_function(self, decl):
		raise NotImplementedError

	def _create_wrapper_for_free_function(self, decl, name=None, orig_cpp_name=None):
		raise NotImplementedError

	def create_wrapper_for_constructor(self, class_decl, constructors):
		raise NotImplementedError

	def create_wrapper_for_nonoverloaded_constructor(self, class_decl, py_name, cons_decl):
		raise NotImplementedError

	def create_special_mul_method(self, cdcl, mdcl):
		raise NotImplementedError

	def create_special_add_method(self, cdcl, mdcl):
		raise NotImplementedError

	def create_special_iadd_method(self, cdcl, mdcl):
		raise NotImplementedError

	def create_special_getitem_method(self, mdcl):
		raise NotImplementedError

	def create_cast_methods(self, mdecls):
		raise NotImplementedError

	def create_special_cmp_method(self, cdcl, ops):
		raise NotImplementedError

	def create_special_copy_method(self, class_decl):
		raise NotImplementedError

	def create_foreign_cimports(self):
		raise NotImplementedError

	def create_cimports(self):
		raise NotImplementedError

	def create_default_cimports(self):
		raise NotImplementedError

	def create_std_cimports(self):
		raise NotImplementedError

	def create_includes(self):
		raise NotImplementedError
