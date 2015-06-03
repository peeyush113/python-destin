"""
@author: Tejas Khot
@contact: tjskhot@gmail.com

@note: An implementation of a general Convolutional Neural Network Layer

TODO:
Add cuda-convnet wrappers from pylearn2 for:
ProbMaxPool, StochasticMaxPool, WeightedMaxPool, CrossMapNorm
preferably in a separate pooling file
"""
import numpy as np
import theano
import theano.tensor as T
from theano.tensor.signal import downsample
from theano.tensor.nnet import conv
from pylearn2.sandbox.cuda_convnet.filter_acts import FilterActs
from theano.sandbox.cuda.basic_ops import gpu_contiguous
from pylearn2.sandbox.cuda_convnet.pool import MaxPool

import general_destin.nnfuns as nnf 
from layer import Layer

class ConvLayer(Layer):
	"""
	This class implements a general layer of ConvNet 
	"""
	def __init__(self,
				 rng,
				 layer_num,
				 feature_maps,
				 feature_shape,
				 filter_shape,
				 pool=False,
				 pool_size=(2,2),
				 stride_size=None,
				 border_mode="valid",
				 **kwargs):
		"""
			   input_size,
               hidden_size,
               is_recursive=False,
               activation_mode="tanh",
               weight_type="none",
               clip_gradients=False,
               clip_bound=1)
		Initialise the ConvNet Layer

		@param rng: random number generator for initializing weights (numpy.random.RandomState)
		@param layer_num: layer number in the Network 
		@param feature_maps: symbolic tensor of shape feature_shape (theano.tensor.dtensor4)
		@param feature_shape: (batch size, number of input feature maps,
		                       image height, image width) (tuple or list of length 4)
		@param filter_shape: (number of filters, number of input feature maps,
		                      filter height, filter width) (tuple or list of length 4)
		@param pool: Indicates if there is a max-pooling process in the layer. (bool)
		@param pool_size: the pooling factor (#rows, #cols) (tuple or list of length 2)
		@param stride_size: the number of shifts over rows/cols to get the the next pool region. 
		                    if st is None, it is considered equal to ds (no overlap on pooling regions) (tuple of size 2) 
		@param border_mode: convolution mode
		                    "valid" for valid convolution
		                    "full" for full convolution (string)  
		"""
		

		self.rng=rng
		self.layer_number=layer_num
		self.in_feature_maps=feature_maps
		self.feature_shape=feature_shape
		self.filter_shape=filter_shape
		self.pool=pool
		self.pool_size=pool_size
		self.stride_size=stride_size
		self.border_mode=border_mode
		
		# generate weights and bias
		# There are (number of input feature maps * filter height * filter width) inputs to each hidden layer
		fan_in = np.prod(filter_shape[1:])
		# each unit in the lower layer receives a gradient from:
		# (number of output feature maps * filter height * filter width) / pooling_size
		fan_out = (filter_shape[0] * np.prod(filter_shape[2:]) / np.prod(pool_size))
		    
		filter_bound = np.sqrt(6. / (fan_in + fan_out))
		self.filters = theano.shared(np.asarray(rng.uniform(low=-filter_bound,
		                                                    high=filter_bound,
		                                                    size=filter_shape),
		                                        			dtype='theano.config.floatX'),
		                             						borrow=True)
		self.filter_bound=filter_bound

		## Generate bias values, initialize as 0
		# the bias is a 1D tensor -- one bias per output feature map
		b_values = np.zeros((filter_shape[0],), dtype='theano.config.floatX')
		self.b = theano.shared(value=b_values, borrow=True)
		
		self.pooled, self.pooled_out=self.get_conv_pool(feature_maps=self.in_feature_maps,
		                                                feature_shape=self.feature_shape,
		                                                filters=self.filters,
		                                                filter_shape=self.filter_shape,
		                                                bias=self.b,
		                                                pool=self.pool,
		                                                pool_size=self.pool_size,
		                                                border_mode=self.border_mode)
		                                   
		self.out_feature_maps=self.get_activation(self.pooled_out)
		
		self.params=[self.filters, self.b]
	
	def get_conv_pool(self,
                      feature_maps,
                      feature_shape,
                      filters,
                      filter_shape,
                      bias,
                      subsample=(1,1),
                      pool=False,
                      pool_size=(2,2),
                	  border_mode="valid"):
		"""
    	Convolution operation in this version is not as powerful as using dnn_conv
    	"""
    	conv_out=conv.conv2d(input=feature_maps,
                         	filters=filters, 
                          	image_shape=feature_shape,
                           	filter_shape=filter_shape,
                            border_mode=border_mode,
                            subsample=subsample);
        if pool==True:
         	pooled_out=downsample.max_pool_2d(input=conv_out,
                                        ds=pool_size);
    	else:
      		pooled_out=conv_out;
      
      	return pooled_out, pooled_out+bias.dimshuffle("x", 0, "x", "x");
   
   	  
	
	
	
	def get_out_feature_maps(self):
	  return self.out_feature_maps
	
	def get_output(self, x):
	  
	  temp, pooled_out=self.get_conv_pool(feature_maps=x,
	                                   feature_shape=self.feature_shape,
	                                   filters=self.filters,
	                                   filter_shape=self.filter_shape,
	                                   bias=self.b,
	                                   pool=self.pool,
	                                   pool_size=self.pool_size,
	                                   border_mode=self.border_mode)
	  
	  return self.get_activation(pooled_out)


class ConvFilterActsLayer(ConvLayer):
	"""
	This class implements a general layer of ConvNet using FilterActs wrapper from pylearn2 sandbox
	"""
	def __init__(self,
				 rng,
				 layer_num,
				 feature_maps,
				 feature_shape,
				 filter_shape,
				 pool=False,
				 pool_size=(2,2),
				 stride_size=None,
				 border_mode="valid",
				 **kwargs):
		"""
		Initialise the ConvNet Layer

		@param rng: random number generator for initializing weights (numpy.random.RandomState)
		@param layer_num: layer number in the Network 
		@param feature_maps: symbolic tensor of shape feature_shape (theano.tensor.dtensor4)
		@param feature_shape: (batch size, number of input feature maps,
		                       image height, image width) (tuple or list of length 4)
		@param filter_shape: (number of filters, number of input feature maps,
		                      filter height, filter width) (tuple or list of length 4)
		@param pool: Indicates if there is a max-pooling process in the layer. (bool)
		@param pool_size: the pooling factor (#rows, #cols) (tuple or list of length 2)
		@param stride_size: the number of shifts over rows/cols to get the the next pool region. 
		                    if st is None, it is considered equal to ds (no overlap on pooling regions) (tuple of size 2) 
		@param border_mode: convolution mode
		                    "valid" for valid convolution
		                    "full" for full convolution (string)  
		
		------------------------------------------------------------------------------
		Optional arguments with **kwargs and their default values:
		
		is_recursive=False,
        activation_mode="tanh",
        weight_type="none",
        clip_gradients=False,
        clip_bound=1
		                    
		"""
		super(ConvFilterActsLayer, self).__init__(rng,
				 								 layer_num,
				 				 				 feature_maps,
				 				 				 feature_shape,
				 				 				 filter_shape,
				 				 				 pool=False,
				 				 				 pool_size=(2,2),
				 				 				 stride_size=None,
				 				 				 border_mode="valid",
				 				 				 **kwargs)
	
	def get_conv_pool(self,
	                  feature_maps,
	                  feature_shape,
	                  filters,
	                  filter_shape,
	                  bias,
	                  subsample=(1,1),
	                  pool=False,
	                  pool_size=(2,2),
	                  border_mode="valid"):
	  
	  	"""
	 	Convolve input feature maps with filters

	 	@param feature_maps: symbolic tensor of shape feature_shape (theano.tensor.dtensor4)
	 	@param feature_shape: (batch size, number of input feature maps,
	 	                       image height, image width) (tuple or list of length 4)
		@param filters: filters generated within bounds
	 	@param filter_shape: (number of filters, number of input feature maps,
	 	                      filter height, filter width) (tuple or list of length 4)
		@param bias: a 1D tensor -- one bias per output feature map
		@param subsample: factor by which to subsample the output (tuple of len 2)
	 	@param pool: Indicates if there is a max-pooling process in the layer. (bool)
	 	@param pool_size: the pooling factor (#rows, #cols) (tuple or list of length 2)
	 	@param border_mode: convolution mode
	 	                    "valid" for valid convolution
	 	                    "full" for full convolution (string)  

	 	--------------------------------------------------------------------
	 	Limitations of using FilterActs compared to conv2d:

	 	> Number of channels <= 3; If you want to compute the gradient, it should be divisible by 4.
	 	> Filters must be square.
	 	> Number of filters must be a multiple of 16
	 	> All minibatch sizes are supported, but the best performance is achieved when the minibatch size 
	 	is a multiple of 128.
	 	> Works only on the GPU

	  	"""
		if theano.config.device!="cpu":
			input=feature_maps
			input_shuffled = input.dimshuffle(1, 2, 3, 0) # bc01 to c01b
			filters_shuffled = filters.dimshuffle(1, 2, 3, 0) # bc01 to c01b
			## Use zero padding with (filter_size - 1) border i.e. full convolution
			if border_mode=="full":
				padding=filter_shape[0]-1
			else:
				padding=0
			conv_out = FilterActs(stride=1, partial_sum=1, pad=padding)
			contiguous_input = gpu_contiguous(input_shuffled)
			contiguous_filters = gpu_contiguous(filters_shuffled)
			conv_out_shuffled = conv_out(contiguous_input, contiguous_filters)
			if pool==True:
				pool_op = MaxPool(ds=poolsize[0], stride=poolsize[0])
				pooled_out_shuffled = pool_op(conv_out_shuffled)
				pooled_out = pooled_out_shuffled.dimshuffle(3, 0, 1, 2) # c01b to bc01
			else:
				pooled_out=conv_out

		else:
			conv_out=conv.conv2d(input=feature_maps,
			 					 filters=filters, 
								 image_shape=feature_shape,
								 filter_shape=filter_shape,
								 border_mode=border_mode,
								 subsample=subsample)

		if pool==True:
			pooled_out=downsample.max_pool_2d(input=conv_out,
			              					  ds=pool_size)
		else:
			pooled_out=conv_out

		return pooled_out, pooled_out+bias.dimshuffle("x", 0, "x", "x")
	

class ConvCuDNNLayer(ConvLayer):
	"""
	This class implements a general layer of ConvNet using cuDNN wrappers from theano sandbox
	This is the fastest convolution implementation
	"""
	def __init__(self,
				 rng,
				 layer_num,
				 feature_maps,
				 feature_shape,
				 filter_shape,
				 pool=False,
				 pool_size=(2,2),
				 stride_size=None,
				 border_mode="valid",
				 **kwargs):
		"""
		Initialize the ConvNet Layer

		@param rng: random number generator for initializing weights (numpy.random.RandomState)
		@param layer_num: layer number in the Network 
		@param feature_maps: symbolic tensor of shape feature_shape (theano.tensor.dtensor4)
		@param feature_shape: (batch size, number of input feature maps,
		                       image height, image width) (tuple or list of length 4)
		@param filter_shape: (number of filters, number of input feature maps,
		                      filter height, filter width) (tuple or list of length 4)
		@param pool: Indicates if there is a max-pooling process in the layer. (bool)
		@param pool_size: the pooling factor (#rows, #cols) (tuple or list of length 2)
		@param stride_size: the number of shifts over rows/cols to get the the next pool region. 
		                    if st is None, it is considered equal to ds (no overlap on pooling regions) (tuple of size 2) 
		@param border_mode: convolution mode
		                    "valid" for valid convolution
		                    "full" for full convolution (string)  
		
		------------------------------------------------------------------------------
		Optional arguments with **kwargs and their default values:
		
		is_recursive=False,
        activation_mode="tanh",
        weight_type="none",
        clip_gradients=False,
        clip_bound=1
		                    
		"""
		super(ConvFilterActsLayer, self).__init__(rng,
				 								 layer_num,
				 				 				 feature_maps,
				 				 				 feature_shape,
				 				 				 filter_shape,
				 				 				 pool=False,
				 				 				 pool_size=(2,2),
				 				 				 stride_size=None,
				 				 				 border_mode="valid",
				 				 				 **kwargs)
	
	def get_conv_pool(self,
	                  feature_maps,
	                  feature_shape,
	                  filters,
	                  filter_shape,
	                  bias,
	                  subsample=(1,1),
	                  pool=False,
	                  pool_size=(2,2),
	                  border_mode="valid"):
	  
	  	"""
	 	Convolve input feature maps with filters

	 	@param feature_maps: symbolic tensor of shape feature_shape (theano.tensor.dtensor4)
	 	@param feature_shape: (batch size, number of input feature maps,
	 	                       image height, image width) (tuple or list of length 4)
		@param filters: filters generated within bounds
	 	@param filter_shape: (number of filters, number of input feature maps,
	 	                      filter height, filter width) (tuple or list of length 4)
		@param bias: a 1D tensor -- one bias per output feature map
		@param subsample: factor by which to subsample the output (tuple of len 2)
	 	@param pool: Indicates if there is a max-pooling process in the layer. (bool)
	 	@param pool_size: the pooling factor (#rows, #cols) (tuple or list of length 2)
	 	@param border_mode: convolution mode
	 	                    "valid" for valid convolution
	 	                    "full" for full convolution (string)  

	 	--------------------------------------------------------------------
	 	Limitations of using FilterActs compared to conv2d:

	 	> Number of channels <= 3; If you want to compute the gradient, it should be divisible by 4.
	 	> Filters must be square.
	 	> Number of filters must be a multiple of 16
	 	> All minibatch sizes are supported, but the best performance is achieved when the minibatch size 
	 	is a multiple of 128.
	 	> Works only on the GPU

	  	"""
	  	if theano.config.device!="cpu":
			input=feature_maps
			input_shuffled = input.dimshuffle(1, 2, 3, 0) # bc01 to c01b
			filters_shuffled = filters.dimshuffle(1, 2, 3, 0) # bc01 to c01b
			## Use zero padding with (filter_size - 1) border i.e. full convolution
			if border_mode=="full":
				padding=filter_shape[0]-1
			else:
				padding=0
			conv_out = FilterActs(stride=1, partial_sum=1, pad=padding)
			contiguous_input = gpu_contiguous(input_shuffled)
			contiguous_filters = gpu_contiguous(filters_shuffled)
			conv_out_shuffled = conv_out(contiguous_input, contiguous_filters)
			if pool==True:
				pool_op = MaxPool(ds=poolsize[0], stride=poolsize[0])
				pooled_out_shuffled = pool_op(conv_out_shuffled)
				pooled_out = pooled_out_shuffled.dimshuffle(3, 0, 1, 2) # c01b to bc01
			else:
				pooled_out=conv_out

		else:
			conv_out=conv.conv2d(input=feature_maps,
			 					 filters=filters, 
								 image_shape=feature_shape,
								 filter_shape=filter_shape,
								 border_mode=border_mode,
								 subsample=subsample)

		if pool==True:
			pooled_out=downsample.max_pool_2d(input=conv_out,
			              					  ds=pool_size)
		else:
			pooled_out=conv_out

		return pooled_out, pooled_out+bias.dimshuffle("x", 0, "x", "x")
	  	



